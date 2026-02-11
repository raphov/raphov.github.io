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
from telegram.error import InvalidToken

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
        self.players: Dict[int, Dict] = {}
        self.ws_connections: List = []
        self.captains: Dict[str, int] = {'red': None, 'blue': None}

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

    def add_player(self, user_id: int, username: str, role: str = 'agent') -> Dict:
        team = self._assign_team()
        player = {
            'id': user_id,
            'username': username,
            'role': role,
            'team': team,
            'joined_at': datetime.now(),
            'is_online': True
        }
        self.players[user_id] = player
        return player

    def _assign_team(self) -> str:
        red = sum(1 for p in self.players.values() if p.get('team') == 'red')
        blue = sum(1 for p in self.players.values() if p.get('team') == 'blue')
        return 'red' if red <= blue else 'blue'

    def set_captain(self, team: str, user_id: int) -> bool:
        if team not in ['red', 'blue'] or user_id not in self.players:
            return False
        self.captains[team] = user_id
        self.players[user_id]['role'] = 'captain'
        self.players[user_id]['team'] = team
        return True

    def get_game_state_for_player(self, user_id: int) -> Dict:
        state = {
            'room_id': self.room_id,
            'words': self.game_state['words'],
            'revealed': self.game_state['revealed'],
            'current_team': self.game_state['current_team'],
            'current_turn': self.game_state['current_turn'],
            'red_score': self.game_state['red_score'],
            'blue_score': self.game_state['blue_score'],
            'game_status': self.game_state['game_status'],
            'winner': self.game_state['winner'],
            'players_count': len(self.players),
            'user_role': self.players.get(user_id, {}).get('role', 'agent'),
            'user_team': self.players.get(user_id, {}).get('team'),
        }
        if user_id in [self.captains['red'], self.captains['blue']]:
            state['colors'] = self.game_state['colors']
        return state

    def reveal_card(self, index: int, user_id: int) -> Dict:
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
            'game_state': self.get_game_state_for_player(user_id),
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
        for ws in self.ws_connections:
            if not ws.closed:
                asyncio.create_task(ws.close())
        self.ws_connections.clear()


active_rooms: Dict[str, GameRoom] = {}


# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================
def make_game_link(room_id: str, user_id: int) -> str:
    return f"{FRONTEND_URL}?room={room_id}&user_id={user_id}"

def escape_html(text: str) -> str:
    """Экранирует спецсимволы для HTML-разметки Telegram"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


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

    keyboard = [
        [InlineKeyboardButton("👑 Стать капитаном", callback_data=f"role_captain_{room_id}"),
         InlineKeyboardButton("🔎 Стать агентом", callback_data=f"role_agent_{room_id}")]
    ]
    await update.message.reply_text(
        f"🎮 <b>НОВАЯ КОМНАТА <code>{room_id}</code></b>\n\n"
        "<b>Выберите роль:</b>\n"
        "• 👑 Капитан – видит цвета карт\n"
        "• 🔎 Агент – угадывает слова\n\n"
        "👇 Нажмите кнопку ниже, чтобы получить личную ссылку.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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
    room = active_rooms[room_id]

    if user.id in room.players:
        # Уже в комнате – сразу ссылка
        link = make_game_link(room_id, user.id)
        await update.message.reply_text(
            f"✅ Вы уже в комнате <code>{room_id}</code>\n\n"
            f"🎮 <b>Ваша ссылка для игры:</b>\n{link}",
            parse_mode='HTML'
        )
        return

    # Добавляем как агента (временная роль)
    player = room.add_player(user.id, user.username or user.first_name, role='agent')

    # Кнопки для выбора капитана, если есть места
    keyboard = []
    captain_btns = []
    if room.captains['red'] is None:
        captain_btns.append(InlineKeyboardButton("👑 Капитан красных", callback_data=f"join_captain_red_{room_id}"))
    if room.captains['blue'] is None:
        captain_btns.append(InlineKeyboardButton("👑 Капитан синих", callback_data=f"join_captain_blue_{room_id}"))
    if captain_btns:
        keyboard.append(captain_btns)
    keyboard.append([InlineKeyboardButton("🔎 Остаться агентом", callback_data=f"join_agent_{room_id}")])

    await update.message.reply_text(
        f"✅ Вы присоединились к комнате <code>{room_id}</code>\n"
        f"Команда: <b>{player['team']}</b>\n\n"
        "Выберите роль или останьтесь агентом:",
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
            text += f"• <code>{rid}</code> – {len(room.players)} игр., {age} мин.\n"
    await update.message.reply_text(text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 <b>Команды:</b>\n"
        "<code>/new</code> – создать комнату\n"
        "<code>/join [код]</code> – присоединиться\n"
        "<code>/list</code> – список комнат\n\n"
        "<b>Как играть:</b>\n"
        "1. Создайте комнату\n"
        "2. Выберите роль (кнопки)\n"
        "3. Получите персональную ссылку\n"
        "4. Пригласите друзей через /join\n"
        "5. Играйте!\n\n"
        "👑 <b>Капитаны</b> видят цвета карт сразу.\n"
        "🔎 <b>Агенты</b> угадывают вслепую.",
        parse_mode='HTML'
    )

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Неизвестная команда. /help",
        parse_mode='HTML'
    )


# ==================== CALLBACK-КНОПКИ ====================
async def role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    parts = data.split('_')
    if len(parts) != 3 or not data.startswith('role_'):
        await query.edit_message_text("❌ Ошибка запроса", parse_mode='HTML')
        return
    role_type, room_id = parts[1], parts[2]
    if room_id not in active_rooms:
        await query.edit_message_text("❌ Комната устарела или не существует", parse_mode='HTML')
        return
    room = active_rooms[room_id]

    if role_type == 'captain':
        team = 'red' if room.captains['red'] is None else 'blue'
        if room.captains[team] is not None:
            await query.edit_message_text(f"❌ Команда {team} уже занята", parse_mode='HTML')
            return
        # Добавляем игрока и назначаем капитаном
        if user.id not in room.players:
            room.add_player(user.id, user.username or user.first_name, role='captain')
        room.set_captain(team, user.id)
        link = make_game_link(room_id, user.id)
        await query.edit_message_text(
            f"✅ <b>Вы капитан команды {team.upper()}!</b>\n\n"
            f"🎮 <b>Ваша ссылка для игры:</b>\n{link}",
            parse_mode='HTML'
        )
    else:  # agent
        if user.id not in room.players:
            player = room.add_player(user.id, user.username or user.first_name, role='agent')
        else:
            player = room.players[user.id]
            player['role'] = 'agent'
        link = make_game_link(room_id, user.id)
        await query.edit_message_text(
            f"✅ <b>Вы агент команды {player['team']}</b>\n\n"
            f"🎮 <b>Ваша ссылка для игры:</b>\n{link}",
            parse_mode='HTML'
        )

async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    parts = data.split('_')
    if len(parts) < 3:
        await query.edit_message_text("❌ Ошибка запроса", parse_mode='HTML')
        return
    role_type = parts[1]
    room_id = parts[-1]
    if room_id not in active_rooms:
        await query.edit_message_text("❌ Комната не найдена", parse_mode='HTML')
        return
    room = active_rooms[room_id]

    if role_type == 'captain':
        team = parts[2]
        if room.captains[team] is not None:
            await query.edit_message_text(f"❌ Капитан {team} уже есть", parse_mode='HTML')
            return
        if user.id not in room.players:
            room.add_player(user.id, user.username or user.first_name, role='captain')
        room.set_captain(team, user.id)
        link = make_game_link(room_id, user.id)
        await query.edit_message_text(
            f"✅ <b>Вы капитан команды {team.upper()}!</b>\n\n"
            f"🎮 <b>Ваша ссылка для игры:</b>\n{link}",
            parse_mode='HTML'
        )
    else:  # agent
        if user.id not in room.players:
            room.add_player(user.id, user.username or user.first_name, role='agent')
        link = make_game_link(room_id, user.id)
        await query.edit_message_text(
            f"✅ <b>Вы агент команды {room.players[user.id]['team']}</b>\n\n"
            f"🎮 <b>Ваша ссылка для игры:</b>\n{link}",
            parse_mode='HTML'
        )


# ==================== WEBSOCKET ====================
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    room_id = request.query.get('room', '').upper()
    user_id = request.query.get('user_id')
    if not room_id or not user_id:
        await ws.close(code=1008, message=b'Need room and user_id')
        return ws
    try:
        uid = int(user_id)
    except ValueError:
        await ws.close(code=1008, message=b'Invalid user_id')
        return ws

    if room_id not in active_rooms:
        await ws.close(code=1008, message=b'Room not found')
        return ws
    room = active_rooms[room_id]
    if uid not in room.players:
        await ws.close(code=1008, message=b'User not in room')
        return ws

    room.ws_connections.append(ws)
    try:
        # Отправляем начальное состояние
        await ws.send_json({
            'type': 'init',
            'game_state': room.get_game_state_for_player(uid)
        })

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                action = data.get('action')
                if action == 'click_card':
                    index = data.get('index')
                    result = room.reveal_card(index, uid)
                    if 'error' in result:
                        await ws.send_json({'type': 'error', 'message': result['error']})
                    else:
                        # Оповещаем всех в комнате
                        for conn in room.ws_connections:
                            if not conn.closed:
                                await conn.send_json({
                                    'type': 'card_revealed',
                                    'index': result['index'],
                                    'color': result['color']
                                })
                        if result['game_over']:
                            for conn in room.ws_connections:
                                if not conn.closed:
                                    await conn.send_json({
                                        'type': 'game_over',
                                        'winner': result['winner']
                                    })
                elif action == 'get_state':
                    await ws.send_json({
                        'type': 'state_update',
                        'game_state': room.get_game_state_for_player(uid)
                    })
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        if ws in room.ws_connections:
            room.ws_connections.remove(ws)
    return ws


# ==================== ВЕБХУК TELEGRAM ====================
async def telegram_webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        return web.Response(text='OK')
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text='Error', status=500)


async def health_check(request):
    return web.Response(text=f"Codenames OK | Rooms: {len(active_rooms)}")


# ==================== ОЧИСТКА СТАРЫХ КОМНАТ ====================
async def cleanup_old_rooms():
    while True:
        await asyncio.sleep(300)
        to_remove = []
        for rid, room in active_rooms.items():
            if not room.is_active():
                room.cleanup()
                to_remove.append(rid)
        for rid in to_remove:
            del active_rooms[rid]
        if to_remove:
            logger.info(f"Очищено {len(to_remove)} устаревших комнат")


# ==================== ЗАПУСК ====================
application = Application.builder().token(BOT_TOKEN).build()

async def main():
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("new", new_command))
    application.add_handler(CommandHandler("join", join_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(role_callback, pattern="^role_"))
    application.add_handler(CallbackQueryHandler(join_callback, pattern="^join_"))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    await application.initialize()
    await application.start()

    # Устанавливаем вебхук (polling НЕ ИСПОЛЬЗУЕМ)
    webhook_url = f"{RENDER_URL}/telegram"
    await application.bot.set_webhook(webhook_url)
    logger.info(f"✅ Вебхук установлен: {webhook_url}")

    # Запускаем aiohttp сервер
    server = web.Application()
    server.router.add_get('/', health_check)
    server.router.add_post('/telegram', telegram_webhook)
    server.router.add_get('/ws', websocket_handler)

    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    # Задача очистки
    asyncio.create_task(cleanup_old_rooms())

    logger.info(f"🚀 Сервер запущен на порту {port}")
    await asyncio.Future()  # работаем вечно

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка по Ctrl+C")
    except Exception as e:
        logger.exception("Критическая ошибка")
