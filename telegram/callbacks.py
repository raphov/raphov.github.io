"""Обработчики callback-кнопок Telegram"""

from telegram import Update
from telegram.ext import ContextTypes
from game.room import GameRoom
from utils.config import FRONTEND_URL

# Глобальное хранилище (будет в main.py)
active_rooms = {}

async def role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора роли при создании комнаты"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    # Формат: role_[type]_[room_id]
    parts = data.split('_')
    if len(parts) != 3:
        await query.edit_message_text("❌ Ошибка обработки запроса")
        return
    
    role_type, room_id = parts[1], parts[2]
    
    if room_id not in active_rooms:
        await query.edit_message_text("❌ Комната устарела или не существует")
        return
    
    room = active_rooms[room_id]
    
    if role_type == 'captain':
        # Автоматически назначаем капитаном в свободную команду
        team = 'red' if room.captains['red'] is None else 'blue'
        
        if room.captains[team] is None:
            player = room.add_player(user.id, user.username or user.first_name, role='captain')
            room.set_captain(team, user.id)
            
            response = (
                f"✅ **{user.first_name} - КАПИТАН КОМАНДЫ {team.upper()}!**\n\n"
                f"**Комната:** `{room_id}`\n"
                f"**Ваша команда:** {team}\n"
                f"**Ваша задача:** Давать подсказки своей команде\n\n"
                f"🎮 **Ссылка на игру:** {FRONTEND_URL}?room={room_id}&user_id={user.id}\n\n"
                f"💡 **Особенности:**\n"
                f"• В игре вы увидите ВСЕ карточки с их цветами\n"
                f"• Открытые карточки будут помечены\n"
                f"• Давайте подсказки из одного слова и числа"
            )
            
        else:
            response = (
                f"❌ **Команда {team.upper()} уже имеет капитана!**\n\n"
                f"Выберите роль агента или создайте новую комнату."
            )
    
    else:  # role_type == 'agent'
        player = room.add_player(user.id, user.username or user.first_name, role='agent')
        team = player['team']
        
        response = (
            f"✅ **{user.first_name} - АГЕНТ!**\n\n"
            f"**Комната:** `{room_id}`\n"
            f"**Ваша команда:** {team}\n"
            f"**Ваша задача:** Угадывать слова по подсказкам капитана\n\n"
            f"🎮 **Ссылка на игру:** {FRONTEND_URL}?room={room_id}&user_id={user.id}\n\n"
            f"💡 **Как играть:**\n"
            f"1. Ждите подсказки от капитана\n"
            f"2. Удерживайте карточку 1.5 секунды для выбора\n"
            f"3. Избегайте чёрной карточки!"
        )
    
    await query.edit_message_text(response, parse_mode='Markdown')

async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора роли при присоединении"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    # Формат: join_[role]_[team?]_[room_id]
    parts = data.split('_')
    
    if len(parts) < 3:
        await query.edit_message_text("❌ Ошибка обработки запроса")
        return
    
    role_type = parts[1]
    room_id = parts[-1]
    
    if room_id not in active_rooms:
        await query.edit_message_text("❌ Комната устарела или не существует")
        return
    
    room = active_rooms[room_id]
    
    if role_type == 'captain':
        team = parts[2]  # red или blue
        
        if room.captains[team] is not None:
            await query.edit_message_text(f"❌ Команда {team} уже имеет капитана!")
            return
        
        player = room.add_player(user.id, user.username or user.first_name, role='captain')
        room.set_captain(team, user.id)
        
        response = (
            f"✅ **{user.first_name} - КАПИТАН КОМАНДЫ {team.upper()}!**\n\n"
            f"**Комната:** `{room_id}`\n"
            f"**Игроков в комнате:** {len(room.players)}\n\n"
            f"🎮 **Ссылка на игру:** {FRONTEND_URL}?room={room_id}&user_id={user.id}\n\n"
            f"💡 **Особенности:**\n"
            f"• Вы видите все цвета карточек сразу\n"
            f"• Давайте подсказки своей команде"
        )
    
    else:  # role_type == 'agent'
        player = room.add_player(user.id, user.username or user.first_name, role='agent')
        team = player['team']
        
        response = (
            f"✅ **{user.first_name} - АГЕНТ!**\n\n"
            f"**Комната:** `{room_id}`\n"
            f"**Ваша команда:** {team}\n"
            f"**Игроков в комнате:** {len(room.players)}\n\n"
            f"🎮 **Ссылка на игру:** {FRONTEND_URL}?room={room_id}&user_id={user.id}\n\n"
            f"💡 **Как играть:**\n"
            f"1. Ждите подсказки от капитана\n"
            f"2. Угадывайте слова своей команды"
        )
    
    await query.edit_message_text(response, parse_mode='Markdown')