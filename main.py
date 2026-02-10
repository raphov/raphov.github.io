#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Codenames Telegram Bot + WebSocket Server
Версия 2.0 - Полная интеграция с фронтендом
"""

import os
import json
import uuid
import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==================== НАСТРОЙКА ЛОГГИРОВАНИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('codenames.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
RENDER_URL = os.environ.get('RENDER_URL', 'https://codenames-u88n.onrender.com')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://raphov.github.io')

# Проверка обязательных переменных
if not BOT_TOKEN:
    logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не задан!")
    print("\n" + "="*70)
    print("ВАЖНО: В настройках Render добавьте переменные окружения:")
    print("1. BOT_TOKEN = ваш_токен_от_BotFather")
    print("2. RENDER_URL = https://codenames-u88n.onrender.com")
    print("3. FRONTEND_URL = https://raphov.github.io")
    print("="*70 + "\n")
    exit(1)

# ==================== ГЛОБАЛЬНЫЕ ХРАНИЛИЩА ====================
class GameRoom:
    """Класс для управления игровой комнатой"""
    
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.created_at = datetime.now()
        self.game_state = self._create_game_state()
        self.players: Dict[int, Dict] = {}  # user_id -> player_data
        self.ws_connections: List[web.WebSocketResponse] = []
        self.captains: Dict[str, int] = {'red': None, 'blue': None}  # team -> user_id
        
    def _create_game_state(self) -> Dict:
        """Создаёт начальное состояние игры"""
        words = self._load_words()
        
        # Создаем ключевую карту: 9 красных, 8 синих, 1 чёрный, 7 нейтральных
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
            'game_status': 'waiting',  # waiting, active, finished
            'winner': None,
            'last_action': None,
            'hint': None,
            'hint_number': None,
            'guesses_left': 0
        }
    
    def _load_words(self) -> List[str]:
        """Загружает список слов из файла или использует стандартный"""
        try:
            with open('words.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # Резервный список слов
            return [
                "яблоко", "гора", "мост", "врач", "луна", "книга", "огонь", "река", "часы",
                "снег", "глаз", "дом", "змея", "кольцо", "корабль", "лев", "лес", "машина",
                "медведь", "нос", "океан", "перо", "пила", "поле", "пуля", "работа", "роза",
                "рука", "сапог", "сок", "стол", "театр", "тень", "фонтан", "хлеб", "школа",
                "шляпа", "ящик", "игла", "йогурт", "зонт", "ксерокс", "эхо", "юла", "якорь",
                "аэропорт", "балерина", "вентилятор", "градусник", "дерево", "ёжик", "железо",
                "замок", "игрушка", "капуста", "лампа", "метро", "ноутбук", "облако", "пальто",
                "ракета", "самолет", "телефон", "улица", "фонарь", "хоккей", "цветок", "человек",
                "шапка", "щука", "экран", "юбка", "язык", "аптека", "бензин", "велосипед", "газета"
            ]
    
    def add_player(self, user_id: int, username: str, role: str = 'agent') -> Dict:
        """Добавляет игрока в комнату"""
        team = self._assign_team()
        player_data = {
            'id': user_id,
            'username': username,
            'role': role,
            'team': team,
            'joined_at': datetime.now(),
            'is_online': True
        }
        self.players[user_id] = player_data
        return player_data
    
    def _assign_team(self) -> str:
        """Распределяет игрока по командам"""
        red_count = sum(1 for p in self.players.values() if p['team'] == 'red')
        blue_count = sum(1 for p in self.players.values() if p['team'] == 'blue')
        return 'red' if red_count <= blue_count else 'blue'
    
    def set_captain(self, team: str, user_id: int) -> bool:
        """Назначает капитана команды"""
        if team not in ['red', 'blue']:
            return False
        
        if user_id not in self.players:
            return False
        
        self.captains[team] = user_id
        self.players[user_id]['role'] = 'captain'
        self.players[user_id]['team'] = team
        return True
    
    def get_key_card_for_captain(self, user_id: int) -> Optional[str]:
        """Возвращает ключевую карту для капитана"""
        if user_id not in [self.captains['red'], self.captains['blue']]:
            return None
        
        # Форматируем ключевую карту в читаемом виде
        game = self.game_state
        key_map = []
        
        for i in range(0, 25, 5):
            row_words = game['words'][i:i+5]
            row_colors = game['colors'][i:i+5]
            row = []
            for word, color in zip(row_words, row_colors):
                if color == 'red':
                    row.append(f"🔴 {word}")
                elif color == 'blue':
                    row.append(f"🔵 {word}")
                elif color == 'black':
                    row.append(f"⚫ {word}")
                else:
                    row.append(f"⚪ {word}")
            key_map.append(" | ".join(row))
        
        team = 'red' if user_id == self.captains['red'] else 'blue'
        opponent_team = 'blue' if team == 'red' else 'red'
        
        message = [
            f"🔐 **КЛЮЧЕВАЯ КАРТА КОМНАТЫ {self.room_id}**",
            f"👑 Вы - капитан команды {team.upper()}",
            "",
            "**Расположение карточек:**",
            *key_map,
            "",
            f"**Ваша команда ({team.upper()}):**",
            f"🔴 Красные: {game['red_score']} слов",
            f"🔵 Синие: {game['blue_score']} слов",
            f"⚫ Убийца: 1 слово",
            f"⚪ Нейтральные: 7 слов",
            "",
            "**Как давать подсказки:**",
            "1. Придумайте слово, связанное с несколькими вашими карточками",
            "2. Укажите количество связанных слов (например: 'лес 3')",
            "3. Ваша команда будет угадывать слова",
            "",
            f"⚠️ **ВНИМАНИЕ:** Не показывайте эту карту {opponent_team} команде!",
            f"🎮 Ссылка на игру: {FRONTEND_URL}?room={self.room_id}"
        ]
        
        return "\n".join(message)
    
    def reveal_card(self, index: int) -> Dict:
        """Открывает карточку и обновляет состояние игры"""
        if not (0 <= index < 25):
            return {'error': 'Invalid index'}
        
        if self.game_state['revealed'][index]:
            return {'error': 'Card already revealed'}
        
        color = self.game_state['colors'][index]
        self.game_state['revealed'][index] = True
        self.game_state['last_action'] = {
            'type': 'card_revealed',
            'index': index,
            'color': color,
            'timestamp': datetime.now().isoformat()
        }
        
        # Обновляем счёт
        if color == 'red':
            self.game_state['red_score'] = max(0, self.game_state['red_score'] - 1)
        elif color == 'blue':
            self.game_state['blue_score'] = max(0, self.game_state['blue_score'] - 1)
        
        # Проверяем условия победы
        result = self._check_winner(color)
        if result['game_over']:
            self.game_state['game_status'] = 'finished'
            self.game_state['winner'] = result['winner']
        
        return {
            'index': index,
            'color': color,
            'game_state': self.get_public_state(),
            'game_over': result['game_over'],
            'winner': result['winner']
        }
    
    def _check_winner(self, last_color: str) -> Dict:
        """Проверяет условия завершения игры"""
        game = self.game_state
        
        # Если открыли чёрную карточку
        if last_color == 'black':
            winner = 'blue' if game['current_team'] == 'red' else 'red'
            return {'game_over': True, 'winner': winner, 'reason': 'assassin'}
        
        # Если одна из команд открыла все свои карточки
        if game['red_score'] == 0:
            return {'game_over': True, 'winner': 'red', 'reason': 'all_found'}
        if game['blue_score'] == 0:
            return {'game_over': True, 'winner': 'blue', 'reason': 'all_found'}
        
        return {'game_over': False, 'winner': None, 'reason': None}
    
    def get_public_state(self) -> Dict:
        """Возвращает публичное состояние игры (без секретной информации)"""
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
            'players_count': len(self.players),
            'captains': {
                'red': self.captains['red'] is not None,
                'blue': self.captains['blue'] is not None
            }
        }
    
    def switch_team(self) -> None:
        """Переключает текущую команду"""
        self.game_state['current_team'] = 'blue' if self.game_state['current_team'] == 'red' else 'red'
        self.game_state['current_turn'] += 1
    
    def is_active(self) -> bool:
        """Проверяет, активна ли комната (не старше 24 часов)"""
        return datetime.now() - self.created_at < timedelta(hours=24)
    
    def cleanup(self) -> None:
        """Очищает ресурсы комнаты"""
        for ws in self.ws_connections:
            if not ws.closed:
                asyncio.create_task(ws.close())
        self.ws_connections.clear()

# Глобальное хранилище комнат
active_rooms: Dict[str, GameRoom] = {}

# ==================== TELEGRAM КОМАНДЫ ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    logger.info(f"User {user.id} (@{user.username}) started the bot")
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

🎮 **Добро пожаловать в Codenames Online!**

📖 **Как играть:**
1. Создайте комнату командой `/new`
2. Выберите роль (Капитан или Агент)
3. Пригласите друзей командой `/join [код]`
4. Начните игру!

🛠 **Доступные команды:**
`/new` - Создать новую комнату
`/join [код]` - Присоединиться к комнате
`/key [код]` - Получить ключевую карту (для капитанов)
`/list` - Список активных комнат
`/help` - Справка по командам

🔗 **Фронтенд:** {FRONTEND_URL}
💡 **Совет:** Капитаны видят цвета всех карточек!
    """
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /new - создание комнаты с выбором роли"""
    user = update.effective_user
    
    # Генерируем уникальный код комнаты
    room_id = str(uuid.uuid4())[:8].upper()
    
    # Создаём комнату
    room = GameRoom(room_id)
    active_rooms[room_id] = room
    
    logger.info(f"User {user.id} created room {room_id}")
    
    # Клавиатура для выбора роли
    keyboard = [
        [
            InlineKeyboardButton("👑 Я буду капитаном", callback_data=f"role_captain_{room_id}"),
            InlineKeyboardButton("🔎 Я буду агентом", callback_data=f"role_agent_{room_id}")
        ]
    ]
    
    message = await update.message.reply_text(
        f"✅ **ИГРОВАЯ КОМНАТА СОЗДАНА!**\n\n"
        f"**Код комнаты:** `{room_id}`\n"
        f"**Ссылка на игру:** {FRONTEND_URL}?room={room_id}\n\n"
        f"**Выберите свою роль:**\n"
        f"• 👑 **Капитан** - видит ключевую карту, даёт подсказки\n"
        f"• 🔎 **Агент** - угадывает слова по подсказкам\n\n"
        f"📋 **Что делать дальше:**\n"
        f"1. Отправьте код `{room_id}` друзьям\n"
        f"2. Попросите их написать `/join {room_id}`\n"
        f"3. Нажмите кнопку с вашей ролью\n"
        f"4. Перейдите по ссылке выше для начала игры",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /join - присоединение к комнате"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Укажите код комнаты!**\n\n"
            "Пример: `/join ABC123`\n"
            "Или создайте свою комнату: `/new`",
            parse_mode='Markdown'
        )
        return
    
    room_id = context.args[0].upper()
    
    if room_id not in active_rooms:
        await update.message.reply_text(
            f"❌ **Комната `{room_id}` не найдена!**\n\n"
            "Возможные причины:\n"
            "• Комната устарела (живёт 24 часа)\n"
            "• Неправильный код комнаты\n"
            "• Комната ещё не создана\n\n"
            "Создайте новую комнату: `/new`",
            parse_mode='Markdown'
        )
        return
    
    room = active_rooms[room_id]
    
    # Проверяем, не присоединялся ли уже пользователь
    if user.id in room.players:
        await update.message.reply_text(
            f"✅ Вы уже в комнате `{room_id}`!\n\n"
            f"🎮 Ссылка на игру: {FRONTEND_URL}?room={room_id}",
            parse_mode='Markdown'
        )
        return
    
    # Добавляем игрока как агента по умолчанию
    player = room.add_player(user.id, user.username or user.first_name, role='agent')
    
    # Клавиатура для выбора роли (если есть свободные места капитанов)
    keyboard = []
    if room.captains['red'] is None:
        keyboard.append([InlineKeyboardButton(
            "👑 Стать капитаном красных", 
            callback_data=f"join_captain_red_{room_id}"
        )])
    if room.captains['blue'] is None:
        keyboard.append([InlineKeyboardButton(
            "👑 Стать капитаном синих", 
            callback_data=f"join_captain_blue_{room_id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        "🔎 Присоединиться как агент", 
        callback_data=f"join_agent_{room_id}"
    )])
    
    response_text = (
        f"✅ **ВЫ ПРИСОЕДИНИЛИСЬ К КОМНАТЕ `{room_id}`!**\n\n"
        f"**Ваша роль:** {player['role']}\n"
        f"**Ваша команда:** {player['team']}\n"
        f"**Игроков в комнате:** {len(room.players)}\n\n"
    )
    
    if keyboard:
        response_text += "**Выберите или подтвердите роль:**"
        await update.message.reply_text(
            response_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        response_text += f"🎮 **Ссылка на игру:** {FRONTEND_URL}?room={room_id}"
        await update.message.reply_text(response_text, parse_mode='Markdown')

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /key - получение ключевой карты"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Укажите код комнаты!**\n\n"
            "Пример: `/key ABC123`\n"
            "Эта команда только для капитанов команд.",
            parse_mode='Markdown'
        )
        return
    
    room_id = context.args[0].upper()
    
    if room_id not in active_rooms:
        await update.message.reply_text(
            f"❌ Комната `{room_id}` не найдена!",
            parse_mode='Markdown'
        )
        return
    
    room = active_rooms[room_id]
    
    # Получаем ключевую карту
    key_card = room.get_key_card_for_captain(user.id)
    
    if key_card:
        await update.message.reply_text(key_card, parse_mode='Markdown')
    else:
        await update.message.reply_text(
            f"❌ **Вы не капитан в комнате `{room_id}`!**\n\n"
            "Только капитаны команд могут видеть ключевую карту.\n"
            "Чтобы стать капитаном:\n"
            "1. Присоединитесь к комнате: `/join {room_id}`\n"
            "2. Выберите роль капитана при присоединении\n"
            "3. Или попросите текущего капитана передать вам роль",
            parse_mode='Markdown'
        )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /list - список активных комнат"""
    if not active_rooms:
        await update.message.reply_text(
            "📭 **Нет активных комнат**\n\n"
            "Создайте первую комнату: `/new`",
            parse_mode='Markdown'
        )
        return
    
    active_list = []
    for room_id, room in list(active_rooms.items()):
        if room.is_active():
            players = len(room.players)
            age = (datetime.now() - room.created_at).seconds // 60
            active_list.append(
                f"• `{room_id}` - {players} игроков, создана {age} мин. назад"
            )
        else:
            # Удаляем устаревшие комнаты
            room.cleanup()
            del active_rooms[room_id]
    
    if active_list:
        await update.message.reply_text(
            "📋 **АКТИВНЫЕ КОМНАТЫ:**\n\n" + "\n".join(active_list) +
            f"\n\n💡 Присоединиться: `/join [код]`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "📭 **Нет активных комнат**\n\n"
            "Создайте первую комнату: `/new`",
            parse_mode='Markdown'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = """
🛠 **КОМАНДЫ БОТА:**

`/start` - Начало работы
`/new` - Создать новую комнату
`/join [код]` - Присоединиться к комнате
`/key [код]` - Получить ключевую карту (капитаны)
`/list` - Список активных комнат
`/help` - Эта справка

🎮 **КАК ИГРАТЬ:**

1. **Создайте комнату** (`/new`)
2. **Выберите роль:**
   • 👑 **Капитан** - видит все цвета, даёт подсказки
   • 🔎 **Агент** - угадывает слова
3. **Пригласите друзей** (`/join [код]`)
4. **Начните игру** по ссылке

🔗 **ВЕБ-ИНТЕРФЕЙС:**
• Открывается автоматически при создании комнаты
• Поддерживает мобильные устройства
• Есть полноэкранный режим
• Поддержка ориентации экрана

💡 **СОВЕТЫ:**
• Капитаны получают ключевую карту в ЛС
• Удерживайте карточку 2 секунды для выбора
• Используйте `/key [код]` для повторного получения карты
• Комнаты живут 24 часа
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ==================== CALLBACK ОБРАБОТЧИКИ ====================
async def role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора роли при создании комнаты"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    # Извлекаем тип роли и ID комнаты
    if data.startswith('role_'):
        parts = data.split('_')
        if len(parts) != 3:
            await query.edit_message_text("❌ Ошибка обработки запроса")
            return
        
        role_type, room_id = parts[1], parts[2]
    
    if room_id not in active_rooms:
        await query.edit_message_text("❌ Комната устарела или не существует")
        return
    
    room = active_rooms[room_id]
    
    # Добавляем игрока с выбранной ролью
    if role_type == 'captain':
        # Автоматически назначаем капитаном в свободную команду
        team = 'red' if room.captains['red'] is None else 'blue'
        if room.captains[team] is None:
            room.set_captain(team, user.id)
            player = room.add_player(user.id, user.username or user.first_name, role='captain')
            
            # Отправляем ключевую карту в ЛС
            key_card = room.get_key_card_for_captain(user.id)
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=key_card,
                    parse_mode='Markdown'
                )
                key_sent = True
            except Exception as e:
                logger.error(f"Failed to send key to {user.id}: {e}")
                key_sent = False
            
            response = (
                f"✅ **ВЫ - КАПИТАН КОМАНДЫ {team.upper()}!**\n\n"
                f"**Комната:** `{room_id}`\n"
                f"**Ваша команда:** {team}\n"
            )
            
            if key_sent:
                response += "🔐 **Ключевая карта отправлена вам в личные сообщения!**\n\n"
            else:
                response += (
                    "⚠️ **Не удалось отправить ключевую карту в ЛС.**\n"
                    "Убедитесь, что вы начали диалог с ботом.\n"
                    "Используйте команду `/key {room_id}` для получения карты.\n\n"
                )
            
            response += (
                f"🎮 **Ссылка на игру:** {FRONTEND_URL}?room={room_id}\n\n"
                f"📋 **Что делать дальше:**\n"
                f"1. Пригласите друзей: `/join {room_id}`\n"
                f"2. Перейдите по ссылке выше\n"
                f"3. Давайте подсказки своей команде!"
            )
            
        else:
            response = (
                f"❌ **Обе команды уже имеют капитанов!**\n\n"
                f"Присоединяйтесь как агент или создайте новую комнату."
            )
    
    else:  # role_type == 'agent'
        player = room.add_player(user.id, user.username or user.first_name, role='agent')
        response = (
            f"✅ **ВЫ - АГЕНТ!**\n\n"
            f"**Комната:** `{room_id}`\n"
            f"**Ваша команда:** {player['team']}\n"
            f"**Ваша задача:** Угадывать слова по подсказкам капитана\n\n"
            f"🎮 **Ссылка на игру:** {FRONTEND_URL}?room={room_id}\n\n"
            f"📋 **Что делать дальше:**\n"
            f"1. Перейдите по ссылке выше\n"
            f"2. Ждите подсказок от капитана\n"
            f"3. Угадывайте слова своей команды!"
        )
    
    await query.edit_message_text(response, parse_mode='Markdown')

async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора роли при присоединении"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    # Извлекаем информацию из callback_data
    # Формат: join_[role]_[team?]_[room_id]
    parts = data.split('_')
    
    if len(parts) < 3:
        await query.edit_message_text("❌ Ошибка обработки запроса")
        return
    
    role_type = parts[1]
    room_id = parts[-1]  # Последняя часть - ID комнаты
    
    if room_id not in active_rooms:
        await query.edit_message_text("❌ Комната устарела или не существует")
        return
    
    room = active_rooms[room_id]
    
    if role_type == 'captain':
        # Определяем команду из callback_data
        team = parts[2]  # red или blue
        
        if room.captains[team] is not None:
            await query.edit_message_text(f"❌ Команда {team} уже имеет капитана!")
            return
        
        room.set_captain(team, user.id)
        player = room.add_player(user.id, user.username or user.first_name, role='captain')
        
        # Отправляем ключевую карту
        key_card = room.get_key_card_for_captain(user.id)
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=key_card,
                parse_mode='Markdown'
            )
            key_sent = True
        except Exception as e:
            logger.error(f"Failed to send key to {user.id}: {e}")
            key_sent = False
        
        response = (
            f"✅ **ВЫ - КАПИТАН КОМАНДЫ {team.upper()}!**\n\n"
            f"**Комната:** `{room_id}`\n"
        )
        
        if key_sent:
            response += "🔐 **Ключевая карта отправлена в ЛС!**\n\n"
        else:
            response += (
                "⚠️ **Не удалось отправить ключевую карту.**\n"
                "Используйте `/key {room_id}` для получения.\n\n"
            )
    
    else:  # role_type == 'agent'
        player = room.add_player(user.id, user.username or user.first_name, role='agent')
        response = (
            f"✅ **ВЫ - АГЕНТ!**\n\n"
            f"**Комната:** `{room_id}`\n"
            f"**Ваша команда:** {player['team']}\n"
        )
    
    response += (
        f"**Игроков в комнате:** {len(room.players)}\n\n"
        f"🎮 **Ссылка на игру:** {FRONTEND_URL}?room={room_id}\n\n"
        f"💡 **Совет:** Нажмите на ссылку или скопируйте её друзьям"
    )
    
    await query.edit_message_text(response, parse_mode='Markdown')

# ==================== WEBSOCKET СЕРВЕР ====================
async def websocket_handler(request):
    """Обработчик WebSocket соединений от фронтенда"""
    ws = web.WebSocketResponse(autoping=True, heartbeat=30, max_msg_size=10*1024*1024)
    await ws.prepare(request)
    
    room_id = request.query.get('room', '').upper()
    client_ip = request.remote
    
    logger.info(f"WebSocket подключение от {client_ip}, комната: '{room_id}'")
    
    # Проверяем комнату
    if not room_id or room_id == 'NULL':
        await ws.close(code=1008, message=b'Room ID required')
        return ws
    
    if room_id not in active_rooms:
        await ws.close(code=1008, message=b'Room not found')
        return ws
    
    room = active_rooms[room_id]
    
    # Регистрируем соединение
    room.ws_connections.append(ws)
    logger.info(f"{client_ip}: Подключён к комнате {room_id} (всего: {len(room.ws_connections)})")
    
    try:
        # Отправляем текущее состояние игры
        await ws.send_json({
            'type': 'init',
            'room': room_id,
            'game_state': room.get_public_state(),
            'timestamp': datetime.now().isoformat()
        })
        
        # Оповещаем других игроков о новом подключении
        await broadcast_to_room(room_id, {
            'type': 'player_joined',
            'players_count': len(room.players),
            'online_count': len(room.ws_connections),
            'timestamp': datetime.now().isoformat()
        })
        
        # Обрабатываем сообщения от клиента
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                await handle_websocket_message(room_id, msg.data, ws)
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket ошибка от {client_ip}: {ws.exception()}")
                break
        
    except Exception as e:
        logger.error(f"Ошибка в WebSocket обработчике ({client_ip}): {e}")
    finally:
        # Удаляем соединение при отключении
        if ws in room.ws_connections:
            room.ws_connections.remove(ws)
            logger.info(f"{client_ip}: Отключён от комнаты {room_id}")
            
            # Уведомляем других игроков об отключении
            await broadcast_to_room(room_id, {
                'type': 'player_left',
                'players_count': len(room.players),
                'online_count': len(room.ws_connections),
                'timestamp': datetime.now().isoformat()
            })
            
            # Если комната пуста более 5 минут - отмечаем для очистки
            if not room.ws_connections:
                logger.info(f"Комната {room_id} пуста (нет активных подключений)")
    
    return ws

async def handle_websocket_message(room_id: str, message: str, ws: web.WebSocketResponse):
    """Обработка сообщений от WebSocket клиентов"""
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
            
            result = room.reveal_card(index)
            
            if 'error' in result:
                await ws.send_json({'type': 'error', 'message': result['error']})
                return
            
            # Рассылаем обновление всем игрокам
           