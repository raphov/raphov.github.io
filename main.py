#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import uuid
import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==================== НАСТРОЙКА ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
RENDER_URL = os.environ.get('RENDER_URL', 'https://codenames-u88n.onrender.com')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://raphov.github.io')

if not BOT_TOKEN:
    logger.critical("❌ BOT_TOKEN не задан!")
    raise ValueError("BOT_TOKEN обязателен")

# ==================== ИГРОВАЯ КОМНАТА ====================
class GameRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.created_at = datetime.now()
        self.game_state = self._create_game_state()
        self.captain_links_used = set()  # просто для статистики, не блокируем

    def _create_game_state(self) -> Dict:
        words = self._load_words()
        colors = (['red'] * 9) + (['blue'] * 8) + ['black'] + (['neutral'] * 7)
        random.shuffle(colors)
        return {
            'words': random.sample(words, 25),
            'colors': colors,
            'revealed': [False] * 25,
            'current_team': 'red',
            'current_turn': 1,
            'red_score': 9,
            'blue_score': 8,
            'game_status': 'waiting',
            'winner': None,
        }

    def _load_words(self) -> List[str]:
        try:
            with open('words.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return ["яблоко", "гора", "мост", "врач", "луна", "книга", "огонь", "река", "часы"]

    def get_captain_state(self) -> Dict:
        """Для капитана - со всеми цветами"""
        state = self.get_public_state()
        state['colors'] = self.game_state['colors']
        state['role'] = 'captain'
        return state

    def get_agent_state(self) -> Dict:
        """Для агента - без цветов"""
        state = self.get_public_state()
        state['role'] = 'agent'
        return state

    def get_public_state(self) -> Dict:
        """Общая часть состояния"""
        return {
            'room_id': self.room_id,
            'words': self.game_state['words'],
            'revealed': self.game_state['revealed'],
            'current_team': self.game_state['current_team'],
            'current_turn': self.game_state['current_turn'],
            'red_score': self.game_state['red_score'],
            'blue_score': self.game_state['blue_score'],
            'game_status': self.game_state['game_status'],
            'winner': self.game_state['winner'],
        }

    def reveal_card(self, index: int) -> Dict:
        if not (0 <= index < 25) or self.game_state['revealed'][index]:
            return {'error': 'Invalid'}
        
        color = self.game_state['colors'][index]
        self.game_state['revealed'][index] = True
        
        if color == 'red':
            self.game_state['red_score'] = max(0, self.game_state['red_score'] - 1)
        elif color == 'blue':
            self.game_state['blue_score'] = max(0, self.game_state['blue_score'] - 1)
        
        result = self._check_winner(color)
        if result['game_over']:
            self.game_state['game_status'] = 'finished'
            self.game_state['winner'] = result['winner']
        
        return {
            'index': index,
            'color': color,
            'game_over': result['game_over'],
            'winner': result['winner']
        }

    def _check_winner(self, last_color: str) -> Dict:
        if last_color == 'black':
            winner = 'blue' if self.game_state['current_team'] == 'red' else 'red'
            return {'game_over': True, 'winner': winner}
        if self.game_state['red_score'] == 0:
            return {'game_over': True, 'winner': 'red'}
        if self.game_state['blue_score'] == 0:
            return {'game_over': True, 'winner': 'blue'}
        return {'game_over': False, 'winner': None}

    def switch_team(self):
        self.game_state['current_team'] = 'blue' if self.game_state['current_team'] == 'red' else 'red'
        self.game_state['current_turn'] += 1

    def is_active(self) -> bool:
        return datetime.now() - self.created_at < timedelta(hours=24)

    def cleanup(self):
        # WebSocket соединения хранятся отдельно, очистим их
        pass


active_rooms: Dict[str, GameRoom] = {}


# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================
def make_captain_link(room_id: str) -> str:
    """Ссылка для капитана - видит все цвета"""
    return f"{FRONTEND_URL}?room={room_id}&role=captain"

def make_agent_link(room_id: str) -> str:
    """Ссылка для агента - видит только слова"""
    return f"{FRONTEND_URL}?room={room_id}&role=agent"


# ==================== КОМАНДЫ TELEGRAM ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Codenames Online</b>\n\n"
        "<code>/new</code> – создать комнату\n"
        "<code>/join [код]</code> – присоединиться\n"
        "<code>/list</code> – список комнат\n"
        "<code>/help</code> – помощь",
        parse_mode='HTML'
    )

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    room_id = str(uuid.uuid4())[:6].upper()
    room = GameRoom(room_id)
    active_rooms[room_id] = room
    logger.info(f"Новая комната {room_id} от {user.id}")

    captain_link = make_captain_link(room_id)
    agent_link = make_agent_link(room_id)

    keyboard = [
        [InlineKeyboardButton("👑 Ссылка для капитана", url=captain_link)],
        [InlineKeyboardButton("🔎 Ссылка для агента", url=agent_link)]
    ]

    await update.message.reply_text(
        f"🎮 <b>КОМНАТА {room_id} СОЗДАНА!</b>\n\n"
        f"<b>👑 Капитан:</b> видит все цвета карточек\n"
        f"<b>🔎 Агент:</b> видит только слова, цвета открываются после клика\n\n"
        f"👇 <b>Отправьте друзьям нужные ссылки:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❓ Укажите код комнаты: <code>/join ABC123</code>",
            parse_mode='HTML'
        )
        return
    
    room_id = context.args[0].upper()
    if room_id not in active_rooms:
        await update.message.reply_text(
            f"❌ Комната <code>{room_id}</code> не найдена",
            parse_mode='HTML'
        )
        return
    
    captain_link = make_captain_link(room_id)
    agent_link = make_agent_link(room_id)
    
    keyboard = [
        [InlineKeyboardButton("👑 Капитан", url=captain_link)],
        [InlineKeyboardButton("🔎 Агент", url=agent_link)]
    ]
    
    await update.message.reply_text(
        f"✅ Комната <code>{room_id}</code>\n\n"
        f"Выберите роль:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not active_rooms:
        await update.message.reply_text("📭 Нет активных комнат", parse_mode='HTML')
        return
    
    text = "📋 <b>Активные комнаты:</b>\n"
    for rid, room in list(active_rooms.items()):
        if room.is_active():
            age = (datetime.now() - room.created_at).seconds // 60
            text += f"• <code>{rid}</code> – создана {age} мин. назад\n"
    await update.message.reply_text(text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 <b>Команды:</b>\n"
        "<code>/new</code> – создать комнату (даёт 2 ссылки)\n"
        "<code>/join [код]</code> – присоединиться к комнате\n"
        "<code>/list</code> – список активных комнат\n\n"
        "<b>Как играть:</b>\n"
        "1. Создайте комнату (/new)\n"
        "2. Отправьте друзьям нужные ссылки\n"
        "3. Капитаны видят ВСЕ цвета сразу\n"
        "4. Агенты угадывают вслепую\n"
        "5. Удерживайте карточку 1.5 сек для выбора",
        parse_mode='HTML'
    )

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Неизвестная команда. /help",
        parse_mode='HTML'
    )


# ==================== WEBSOCKET ====================
async def websocket_handler(request):
    """WebSocket обработчик - БЕЗ user_id, только по комнате и роли"""
    
    # Разрешаем CORS
    if request.method == "OPTIONS":
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    ws = web.WebSocketResponse(autoping=True, heartbeat=30)
    
    try:
        await ws.prepare(request)
    except Exception as e:
        logger.error(f"❌ Ошибка подготовки WebSocket: {e}")
        return web.Response(status=500, text="WebSocket preparation failed")

    room_id = request.query.get('room', '').upper()
    role = request.query.get('role', 'agent')  # captain или agent
    
    logger.info(f"🔌 WebSocket: комната={room_id}, роль={role}, origin={request.headers.get('Origin', 'unknown')}")

    if not room_id:
        await ws.close(code=1008, message=b'Room ID required')
        return ws

    if room_id not in active_rooms:
        logger.error(f"❌ Комната {room_id} не найдена")
        await ws.close(code=1008, message=b'Room not found')
        return ws

    room = active_rooms[room_id]
    
    # Сохраняем соединение для рассылки
    if not hasattr(room, 'ws_connections'):
        room.ws_connections = []
    room.ws_connections.append(ws)
    
    logger.info(f"✅ WebSocket подключен: комната {room_id}, роль {role}, всего соединений: {len(room.ws_connections)}")

    try:
        # Отправляем начальное состояние в зависимости от роли
        if role == 'captain':
            game_state = room.get_captain_state()
        else:
            game_state = room.get_agent_state()
        
        await ws.send_json({
            'type': 'init',
            'game_state': game_state
        })

        # Обрабатываем сообщения
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    action = data.get('action')
                    
                    if action == 'click_card':
                        index = data.get('index')
                        if index is not None:
                            result = room.reveal_card(index)
                            
                            if 'error' in result:
                                await ws.send_json({'type': 'error', 'message': result['error']})
                            else:
                                # Рассылаем обновление ВСЕМ в комнате
                                update_msg = {
                                    'type': 'card_revealed',
                                    'index': result['index'],
                                    'color': result['color']
                                }
                                
                                for conn in room.ws_connections:
                                    if not conn.closed:
                                        await conn.send_json(update_msg)
                                
                                # Проверяем конец игры
                                if result['game_over']:
                                    game_over_msg = {
                                        'type': 'game_over',
                                        'winner': result['winner']
                                    }
                                    for conn in room.ws_connections:
                                        if not conn.closed:
                                            await conn.send_json(game_over_msg)
                                
                                # Переключаем команду при необходимости
                                elif result['color'] not in [room.game_state['current_team'], 'neutral', 'black']:
                                    room.switch_team()
                                    turn_msg = {
                                        'type': 'turn_switch',
                                        'current_team': room.game_state['current_team'],
                                        'current_turn': room.game_state['current_turn']
                                    }
                                    for conn in room.ws_connections:
                                        if not conn.closed:
                                            await conn.send_json(turn_msg)
                    
                    elif action == 'get_state':
                        if role == 'captain':
                            await ws.send_json({
                                'type': 'state_update',
                                'game_state': room.get_captain_state()
                            })
                        else:
                            await ws.send_json({
                                'type': 'state_update',
                                'game_state': room.get_agent_state()
                            })
                    
                    elif action == 'ping':
                        await ws.send_json({'type': 'pong'})
                        
                except json.JSONDecodeError:
                    logger.error(f"❌ JSON ошибка")
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки: {e}")
            
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"❌ WebSocket ошибка: {ws.exception()}")

    except Exception as e:
        logger.error(f"❌ WebSocket ошибка: {e}")
    finally:
        if ws in room.ws_connections:
            room.ws_connections.remove(ws)
            logger.info(f"🔌 WebSocket отключен: комната {room_id}, осталось: {len(room.ws_connections)}")
    
    return ws


# ==================== HTTP ЭНДПОИНТЫ ====================
async def telegram_webhook(request):
    """Обработчик вебхука Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        return web.Response(text='OK')
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return web.Response(text='Error', status=500)

async def health_check(request):
    """Проверка работоспособности"""
    total_connections = 0
    for room in active_rooms.values():
        if hasattr(room, 'ws_connections'):
            total_connections += len(room.ws_connections)
    
    return web.json_response({
        'status': 'ok',
        'rooms': len(active_rooms),
        'connections': total_connections,
        'timestamp': datetime.now().isoformat()
    })

async def debug_rooms(request):
    """Отладка - список комнат"""
    rooms_info = []
    for rid, room in active_rooms.items():
        rooms_info.append({
            'room_id': rid,
            'connections': len(getattr(room, 'ws_connections', [])),
            'red_score': room.game_state['red_score'],
            'blue_score': room.game_state['blue_score'],
            'revealed': sum(room.game_state['revealed']),
            'created': room.created_at.isoformat(),
            'active': room.is_active()
        })
    return web.json_response(rooms_info)

async def cors_handler(request):
    """CORS для предварительных запросов"""
    return web.Response(
        status=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )


# ==================== ОЧИСТКА ====================
async def cleanup_old_rooms():
    """Периодическая очистка старых комнат"""
    while True:
        await asyncio.sleep(300)
        to_remove = []
        for rid, room in active_rooms.items():
            if not room.is_active():
                if hasattr(room, 'ws_connections'):
                    for ws in room.ws_connections:
                        if not ws.closed:
                            await ws.close()
                to_remove.append(rid)
        
        for rid in to_remove:
            del active_rooms[rid]
        
        if to_remove:
            logger.info(f"🧹 Очищено {len(to_remove)} устаревших комнат")


# ==================== ЗАПУСК ====================
application = Application.builder().token(BOT_TOKEN).build()

async def main():
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("new", new_command))
    application.add_handler(CommandHandler("join", join_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    await application.initialize()
    await application.start()

    # Устанавливаем вебхук
    webhook_url = f"{RENDER_URL}/telegram"
    await application.bot.set_webhook(webhook_url)
    logger.info(f"✅ Вебхук установлен: {webhook_url}")

    # Создаем aiohttp сервер
    server = web.Application()
    
    # CORS middleware
    async def cors_middleware(request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    
    server.middlewares.append(cors_middleware)
    
    # Регистрируем маршруты
    server.router.add_get('/', health_check)
    server.router.add_get('/health', health_check)
    server.router.add_get('/debug', debug_rooms)
    server.router.add_post('/telegram', telegram_webhook)
    server.router.add_get('/ws', websocket_handler)
    server.router.add_options('/{tail:.*}', cors_handler)

    # Запускаем сервер
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    # Запускаем очистку
    asyncio.create_task(cleanup_old_rooms())

    logger.info(f"🚀 Сервер запущен на порту {port}")
    logger.info(f"🔌 WebSocket: {RENDER_URL.replace('https://', '')}/ws?room=КОМНАТА&role=РОЛЬ")
    
    await asyncio.Future()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Остановка по Ctrl+C")
    except Exception as e:
        logger.exception("❌ Критическая ошибка")
