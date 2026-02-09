import os, json, uuid, random
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext
from aiohttp.web_runner import TCPSite

# --- Конфигурация ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://your-username.github.io')  # Ваш GitHub Pages
PORT = int(os.getenv('PORT', 8080))

# --- Хранилище данных игры ---
active_games = {}  # room_id -> game_state
ws_connections = {}  # room_id -> [WebSocketResponse, ]

# --- Логика игры ---
WORD_LIST = [
    "яблоко", "гора", "мост", "врач", "луна", "книга", "огонь", "река", "часы", "снег",
    "глаз", "дом", "змея", "кольцо", "корабль", "лев", "лес", "машина", "медведь", "нос",
    "океан", "перо", "пила", "поле", "пуля", "работа", "роза", "рука", "сапог", "сок",
    "стол", "театр", "тень", "фонтан", "хлеб", "школа", "шляпа", "ящик"
]

def generate_game_state():
    words = random.sample(WORD_LIST, 25)
    # Ключевая карта: 9 красных, 8 синих, 1 чёрный (убийца), 7 нейтральных
    key = (['red'] * 9) + (['blue'] * 8) + ['black'] + (['neutral'] * 7)
    random.shuffle(key)
    return {
        'words': words,
        'key': key,
        'revealed': [False] * 25,
        'current_team': 'red',  # Красные начинают
        'hint': None,
        'hint_number': None,
        'guesses_left': 0,
        'status': 'waiting'  # waiting -> hint -> guessing -> finished
    }

# --- Обработчики команд Telegram ---
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🎮 Добро пожаловать в Codenames!\n"
        "Создайте новую игру: /newgame\n"
        "Присоединиться к комнате: /join [room_id]"
    )

async def newgame(update: Update, context: CallbackContext):
    room_id = str(uuid.uuid4())[:8]
    active_games[room_id] = generate_game_state()
    game_url = f"{FRONTEND_URL}/?room={room_id}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎮 Открыть игровое поле", url=game_url)
    ]])
    await update.message.reply_text(
        f"✅ Игра создана! Комната: `{room_id}`\n"
        "Отправьте этот ID друзьям для присоединения.\n"
        "Нажмите кнопку ниже, чтобы открыть игровое поле:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def join(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("Укажите ID комнаты: /join ABC123")
        return
    room_id = context.args[0]
    if room_id not in active_games:
        await update.message.reply_text("❌ Комната не найдена!")
        return
    game_url = f"{FRONTEND_URL}/?room={room_id}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎮 Присоединиться к игре", url=game_url)
    ]])
    await update.message.reply_text(
        f"Вы присоединились к комнате `{room_id}`!",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# --- WebSocket сервер (обработчик) ---
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    room_id = request.query.get('room')
    if not room_id or room_id not in active_games:
        await ws.close(code=1008, message=b'Invalid room')
        return ws
    # Регистрируем соединение в комнате
    if room_id not in ws_connections:
        ws_connections[room_id] = []
    ws_connections[room_id].append(ws)
    try:
        # Отправляем текущее состояние новому игроку
        await ws.send_json({
            'type': 'state_update',
            'game': active_games[room_id]
        })
        # Обрабатываем сообщения от клиента
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                await handle_game_action(room_id, data, ws)
    finally:
        # Удаляем соединение при отключении
        ws_connections[room_id].remove(ws)
        if not ws_connections[room_id]:
            del ws_connections[room_id]
    return ws

async def handle_game_action(room_id, data, ws):
    game = active_games.get(room_id)
    if not game:
        return
    action = data.get('action')
    # Пример обработки действия "открыть карточку"
    if action == 'reveal':
        index = data['index']
        if 0 <= index < 25 and not game['revealed'][index]:
            game['revealed'][index] = True
            color = game['key'][index]
            # Рассылаем обновление всем в комнате
            await broadcast(room_id, {
                'type': 'card_revealed',
                'index': index,
                'color': color
            })
            # Проверяем условия победы/поражения
            await check_game_over(room_id, color)

async def broadcast(room_id, message):
    if room_id in ws_connections:
        for ws in ws_connections[room_id]:
            try:
                await ws.send_json(message)
            except:
                pass

async def check_game_over(room_id, last_color):
    game = active_games[room_id]
    # Логика проверки победы (упрощённая)
    red_remaining = sum(1 for i, c in enumerate(game['key']) if c == 'red' and not game['revealed'][i])
    blue_remaining = sum(1 for i, c in enumerate(game['key']) if c == 'blue' and not game['revealed'][i])
    if last_color == 'black':
        winner = 'blue' if game['current_team'] == 'red' else 'red'
        await broadcast(room_id, {'type': 'game_over', 'winner': winner, 'reason': 'assassin'})
    elif red_remaining == 0:
        await broadcast(room_id, {'type': 'game_over', 'winner': 'red', 'reason': 'all_found'})
    elif blue_remaining == 0:
        await broadcast(room_id, {'type': 'game_over', 'winner': 'blue', 'reason': 'all_found'})

# --- Запуск приложения ---
async def main():
    # Инициализация Telegram бота
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    # Запуск бота в фоне
    await app.initialize()
    updater = await app.updater.start_polling()
    # Настройка HTTP и WebSocket сервера
    aiohttp_app = web.Application()
    aiohttp_app.router.add_get('/ws', websocket_handler)
    runner = web.AppRunner(aiohttp_app)
    await runner.setup()
    site = TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"🚀 Сервер запущен на порту {PORT}")
    print(f"🤖 Бот активен. WebSocket endpoint: /ws")
    # Бесконечное ожидание
    await asyncio.Event().wait()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())