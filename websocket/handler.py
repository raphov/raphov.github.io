"""WebSocket обработчик для игры"""

import json
import asyncio
from datetime import datetime
from aiohttp import web
from game.room import GameRoom

# Глобальное хранилище (будет в main.py)
active_rooms = {}

async def websocket_handler(request):
    """Обработчик WebSocket соединений"""
    ws = web.WebSocketResponse(autoping=True, heartbeat=30)
    await ws.prepare(request)
    
    room_id = request.query.get('room', '').upper()
    user_id = request.query.get('user_id')
    
    if not room_id or not user_id:
        await ws.close(code=1008, message=b'Room ID and User ID required')
        return ws
    
    if room_id not in active_rooms:
        await ws.close(code=1008, message=b'Room not found')
        return ws
    
    room = active_rooms[room_id]
    
    # Проверяем, зарегистрирован ли пользователь
    try:
        user_id_int = int(user_id)
    except ValueError:
        await ws.close(code=1008, message=b'Invalid User ID')
        return ws
    
    if user_id_int not in room.players:
        await ws.close(code=1008, message=b'User not in room')
        return ws
    
    # Регистрируем соединение
    room.ws_connections.append(ws)
    
    try:
        # Отправляем текущее состояние игры для этого пользователя
        game_state = room.get_game_state_for_player(user_id_int)
        await ws.send_json({
            'type': 'init',
            'room': room_id,
            'game_state': game_state,
            'timestamp': datetime.now().isoformat()
        })
        
        # Оповещаем других игроков о новом подключении
        await broadcast_to_room(room_id, {
            'type': 'player_joined',
            'players_count': len(room.players),
            'online_count': len(room.ws_connections),
            'timestamp': datetime.now().isoformat()
        }, exclude_ws=ws)
        
        # Обрабатываем сообщения от клиента
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                await handle_websocket_message(room_id, user_id_int, msg.data, ws)
            elif msg.type == web.WSMsgType.ERROR:
                break
        
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Удаляем соединение
        if ws in room.ws_connections:
            room.ws_connections.remove(ws)
            
            # Уведомляем об отключении
            await broadcast_to_room(room_id, {
                'type': 'player_left',
                'players_count': len(room.players),
                'online_count': len(room.ws_connections),
                'timestamp': datetime.now().isoformat()
            })
    
    return ws

async def handle_websocket_message(room_id: str, user_id: int, message: str, ws: web.WebSocketResponse):
    """Обработка сообщений от клиента"""
    try:
        data = json.loads(message)
        action = data.get('action')
        
        if room_id not in active_rooms:
            await ws.send_json({'type': 'error', 'message': 'Room not found'})
            return
        
        room = active_rooms[room_id]
        
        if action == 'click_card':
            index = data.get('index')
            if index is None:
                return
            
            result = room.reveal_card(index, user_id)
            
            if 'error' in result:
                await ws.send_json({'type': 'error', 'message': result['error']})
                return
            
            # Рассылаем обновление всем игрокам
            await broadcast_to_room(room_id, {
                'type': 'card_revealed',
                'index': result['index'],
                'color': result['color'],
                'user_id': user_id,
                'timestamp': datetime.now().isoformat()
            })
            
            # Если игра окончена
            if result['game_over']:
                await broadcast_to_room(room_id, {
                    'type': 'game_over',
                    'winner': result['winner'],
                    'game_state': room.get_game_state_for_player(user_id),
                    'timestamp': datetime.now().isoformat()
                })
                
                # Удаляем комнату через 30 секунд
                asyncio.create_task(cleanup_room_after_delay(room_id, 30))
            
            # Переключаем команду, если нужно
            elif result['color'] not in [room.game_state['current_team'], 'neutral', 'black']:
                room.switch_team()
                
                await broadcast_to_room(room_id, {
                    'type': 'turn_switch',
                    'current_team': room.game_state['current_team'],
                    'current_turn': room.game_state['current_turn'],
                    'timestamp': datetime.now().isoformat()
                })
        
        elif action == 'get_state':
            # Отправляем состояние для конкретного пользователя
            game_state = room.get_game_state_for_player(user_id)
            await ws.send_json({
                'type': 'state_update',
                'game_state': game_state,
                'timestamp': datetime.now().isoformat()
            })
        
        elif action == 'ping':
            await ws.send_json({
                'type': 'pong',
                'timestamp': datetime.now().isoformat()
            })
    
    except json.JSONDecodeError:
        await ws.send_json({'type': 'error', 'message': 'Invalid JSON'})
    except Exception as e:
        print(f"Error handling message: {e}")
        await ws.send_json({'type': 'error', 'message': 'Internal server error'})

async def broadcast_to_room(room_id: str, message: dict, exclude_ws=None):
    """Рассылка сообщения всем в комнате"""
    if room_id not in active_rooms:
        return
    
    room = active_rooms[room_id]
    disconnected = []
    
    for ws in room.ws_connections:
        if ws == exclude_ws:
            continue
            
        if not ws.closed:
            try:
                await ws.send_json(message)
            except:
                disconnected.append(ws)
        else:
            disconnected.append(ws)
    
    # Удаляем отключённые соединения
    for ws in disconnected:
        if ws in room.ws_connections:
            room.ws_connections.remove(ws)

async def cleanup_room_after_delay(room_id: str, delay_seconds: int):
    """Удаляет комнату через указанное время"""
    await asyncio.sleep(delay_seconds)
    
    if room_id in active_rooms:
        room = active_rooms[room_id]
        if not room.ws_connections:
            room.cleanup()
            del active_rooms[room_id]