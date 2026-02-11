"""Обработчики команд Telegram бота"""

import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from game.room import GameRoom
from telegram.keyboard import create_role_keyboard
from utils.config import FRONTEND_URL

# Глобальное хранилище (будет в main.py)
active_rooms = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

🎮 **Добро пожаловать в Codenames Online!**

📖 **Как играть:**
1. Создайте комнату командой `/new`
2. Выберите роль (Капитан или Агент)
3. Пригласите друзей командой `/join [код]`
4. Начните игру по ссылке!

🛠 **Доступные команды:**
`/new` - Создать новую комнату
`/join [код]` - Присоединиться к комнате
`/list` - Список активных комнат
`/help` - Справка по командам

🔗 **Фронтенд:** {FRONTEND_URL}
💡 **Капитаны видят все цвета сразу в игре!**
"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Создание новой комнаты"""
    user = update.effective_user
    
    # Генерируем код комнаты
    room_id = str(uuid.uuid4())[:6].upper()
    
    # Создаём комнату
    room = GameRoom(room_id)
    active_rooms[room_id] = room
    
    # Клавиатура для выбора роли
    keyboard = create_role_keyboard(room_id, is_new=True)
    
    message = await update.message.reply_text(
        f"🎮 **НОВАЯ ИГРОВАЯ КОМНАТА СОЗДАНА!**\n\n"
        f"**Код комнаты:** `{room_id}`\n"
        f"**Ссылка для всех:** {FRONTEND_URL}?room={room_id}\n\n"
        f"**Выберите свою роль:**\n"
        f"• 👑 **Капитан** - видит ВСЕ цвета карточек в игре\n"
        f"• 🔎 **Агент** - видит только слова, цвета открываются после клика\n\n"
        f"📋 **Что делать дальше:**\n"
        f"1. Пригласите друзей: `/join {room_id}`\n"
        f"2. Выберите роль кнопками ниже\n"
        f"3. Перейдите по ссылке для начала игры",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Присоединение к существующей комнате"""
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text(
            "🎮 **Присоединиться к игре**\n\n"
            "Укажите код комнаты:\n"
            "`/join ABC123`\n\n"
            "Или создайте свою комнату:\n"
            "`/new`",
            parse_mode='Markdown'
        )
        return
    
    room_id = context.args[0].upper()
    
    if room_id not in active_rooms:
        await update.message.reply_text(
            f"❌ **Комната `{room_id}` не найдена!**\n\n"
            "Возможные причины:\n"
            "• Комната устарела (живёт 24 часа)\n"
            "• Неправильный код\n"
            "• Комната ещё не создана\n\n"
            "Создайте новую комнату: `/new`",
            parse_mode='Markdown'
        )
        return
    
    room = active_rooms[room_id]
    
    # Проверяем, не присоединялся ли уже пользователь
    if user.id in room.players:
        await update.message.reply_text(
            f"✅ **Вы уже в комнате `{room_id}`!**\n\n"
            f"🎮 Ссылка на игру: {FRONTEND_URL}?room={room_id}",
            parse_mode='Markdown'
        )
        return
    
    # Создаём кнопки для выбора роли
    keyboard = create_role_keyboard(room_id, is_new=False, room=room)
    
    await update.message.reply_text(
        f"✅ **{user.first_name}, вы присоединились к комнате `{room_id}`!**\n\n"
        f"**Сейчас в комнате:** {len(room.players)} игроков\n"
        f"🎮 **Ссылка на игру:** {FRONTEND_URL}?room={room_id}\n\n"
        "**Выберите роль:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список активных комнат"""
    from datetime import datetime
    
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
    """Справка по командам"""
    help_text = """
🛠 **КОМАНДЫ БОТА:**

`/start` - Начало работы
`/new` - Создать новую комнату
`/join [код]` - Присоединиться к комнате
`/list` - Список активных комнат
`/help` - Эта справка

🎮 **КАК ИГРАТЬ:**

1. **Создайте комнату** (`/new`)
2. **Выберите роль:**
   • 👑 **Капитан** - видит все цвета карточек сразу
   • 🔎 **Агент** - видит только слова
3. **Пригласите друзей** (`/join [код]`)
4. **Начните игру** по ссылке

💡 **ОСОБЕННОСТИ:**
• Капитаны видят цвета всех карточек в веб-интерфейсе
• Агенты видят цвета только после открытия карточки
• Чёрная карточка = мгновенное поражение
• Удерживайте карточку 1.5 секунды для выбора
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных команд"""
    await update.message.reply_text(
        "❓ Неизвестная команда.\n\n"
        "Доступные команды:\n"
        "`/start` - Начало работы\n"
        "`/new` - Создать комнату\n"
        "`/join [код]` - Присоединиться\n"
        "`/list` - Список комнат\n"
        "`/help` - Справка",
        parse_mode='Markdown'
    )