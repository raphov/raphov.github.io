"""Обработчики callback-кнопок Telegram"""

from telegram import Update
from telegram.ext import ContextTypes
from game.room import GameRoom
from utils.config import FRONTEND_URL

# Глобальное хранилище (будет в main.py)
active_rooms = {}

async def role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    _, role, room_id = query.data.split('_')

    if room_id not in active_rooms:
        await query.edit_message_text("❌ Комната устарела")
        return

    room = active_rooms[room_id]

    if role == 'captain':
        team = 'red' if room.captains['red'] is None else 'blue'
        if room.captains[team] is not None:
            await query.edit_message_text(f"❌ Капитан {team} уже занят")
            return
        room.add_player(user.id, user.username or user.first_name, role='captain')
        room.set_captain(team, user.id)
        link = make_game_link(room_id, user.id)
        await query.edit_message_text(
            f"✅ **{user.first_name}, вы капитан {team.upper()}!**\n\n"
            f"🎮 **Ваша ссылка:**\n{link}",
            parse_mode='Markdown'
        )
    else:  # agent
        room.add_player(user.id, user.username or user.first_name, role='agent')
        link = make_game_link(room_id, user.id)
        await query.edit_message_text(
            f"✅ **{user.first_name}, вы агент команды {room.players[user.id]['team']}**\n\n"
            f"🎮 **Ваша ссылка:**\n{link}",
            parse_mode='Markdown'
        )


async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    parts = query.data.split('_')
    role_type = parts[1]
    room_id = parts[-1]

    if room_id not in active_rooms:
        await query.edit_message_text("❌ Комната не найдена")
        return

    room = active_rooms[room_id]

    if role_type == 'captain':
        team = parts[2]
        if room.captains[team] is not None:
            await query.edit_message_text(f"❌ Капитан {team} уже есть")
            return
        # обновляем роль у уже добавленного игрока
        if user.id in room.players:
            room.players[user.id]['role'] = 'captain'
            room.players[user.id]['team'] = team
        else:
            room.add_player(user.id, user.username or user.first_name, role='captain')
        room.set_captain(team, user.id)
        link = make_game_link(room_id, user.id)
        await query.edit_message_text(
            f"✅ **{user.first_name}, вы капитан {team.upper()}!**\n\n"
            f"🎮 **Ссылка:**\n{link}",
            parse_mode='Markdown'
        )
    else:  # agent
        # уже добавлен в join_command, просто даём ссылку
        link = make_game_link(room_id, user.id)
        await query.edit_message_text(
            f"✅ **{user.first_name}, вы агент команды {room.players[user.id]['team']}**\n\n"
            f"🎮 **Ссылка:**\n{link}",
            parse_mode='Markdown'
        )
    
    await query.edit_message_text(response, parse_mode='Markdown')