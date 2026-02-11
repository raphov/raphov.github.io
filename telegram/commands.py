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

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    room_id = str(uuid.uuid4())[:6].upper()
    room = GameRoom(room_id)
    active_rooms[room_id] = room

    keyboard = [
        [InlineKeyboardButton("👑 Капитан", callback_data=f"role_captain_{room_id}"),
         InlineKeyboardButton("🔎 Агент", callback_data=f"role_agent_{room_id}")]
    ]

    await update.message.reply_text(
        f"🎮 **НОВАЯ КОМНАТА**\n\n"
        f"**Код:** `{room_id}`\n\n"
        f"Выберите роль:\n"
        f"• 👑 Капитан – видит все цвета в игре\n"
        f"• 🔎 Агент – угадывает вслепую\n\n"
        f"📌 После выбора вы получите личную ссылку.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Укажите код: `/join ABC123`", parse_mode='Markdown')
        return

    room_id = context.args[0].upper()
    if room_id not in active_rooms:
        await update.message.reply_text(f"❌ Комната `{room_id}` не найдена", parse_mode='Markdown')
        return

    room = active_rooms[room_id]

    # Если уже в комнате → сразу ссылка
    if user.id in room.players:
        link = make_game_link(room_id, user.id)
        await update.message.reply_text(
            f"✅ Вы уже в комнате `{room_id}`\n\n"
            f"🎮 **Ваша ссылка:**\n{link}",
            parse_mode='Markdown'
        )
        return

    # Добавляем как агента по умолчанию
    room.add_player(user.id, user.username or user.first_name, role='agent')

    # Кнопки, если есть свободные капитаны
    keyboard = []
    captain_buttons = []
    if room.captains['red'] is None:
        captain_buttons.append(InlineKeyboardButton("👑 Капитан красных", callback_data=f"join_captain_red_{room_id}"))
    if room.captains['blue'] is None:
        captain_buttons.append(InlineKeyboardButton("👑 Капитан синих", callback_data=f"join_captain_blue_{room_id}"))
    if captain_buttons:
        keyboard.append(captain_buttons)
    keyboard.append([InlineKeyboardButton("🔎 Остаться агентом", callback_data=f"join_agent_{room_id}")])

    await update.message.reply_text(
        f"✅ **{user.first_name}, вы в комнате `{room_id}`**\n\n"
        f"Ваша команда: {room.players[user.id]['team']}\n"
        f"Выберите роль или оставайтесь агентом:",
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