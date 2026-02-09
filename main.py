import os, json, uuid, random, asyncio, logging
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, TypeHandler

# --- Настройка логирования ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация (Заполнить в Render!) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')           # Токен из @BotFather
RENDER_URL = os.environ.get('RENDER_URL')         # https://ваш-проект.onrender.com
FRONTEND_URL = os.environ.get('FRONTEND_URL')     # https://username.github.io

# --- Хранилище данных игры ---
active_games = {}
ws_connections = {}

WORD_LIST = [
    "яблоко", "гора", "мост", "врач", "луна", "книга", "огонь", "река", "часы", "снег",
    "глаз", "дом", "змея", "кольцо", "корабль", "лев", "лес", "машина", "медведь", "нос",
    "океан", "перо", "пила", "поле", "пуля", "работа", "роза", "рука", "сапог", "сок",
    "стол", "театр", "тень", "фонтан", "хлеб", "школа", "шляпа", "ящик", "игла", "йогурт",
    "зонт", "ксерокс", "эхо", "юла", "якорь"
]

def generate_game_state():
    """Создаёт новое состояние игры"""
    words = random.sample(WORD_LIST, 25)
    # Распределение: 9 красных, 8 синих, 1 чёрный, 7 нейтральных
    key = (['red'] * 9) + (['blue'] * 8) + ['black'] + (['neutral'] * 7)
    random.shuffle(key)
    
    return {
        'words': words,
        'key': key,
        'revealed': [False] * 25,
        'current_team': 'red',
        'hint': None,
        'hint_number': None,
        'guesses_left': 0,
        'status': 'waiting',
        'players': []
    }

# --- Команды Telegram ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    await update.message.reply_text(
        "🎮 Добро пожаловать в Codenames!\n"
        "Создать игру: /newgame\n"
        "Присоединиться: /join [ID комнаты]"
    )

async def newgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /newgame"""
    room_id = str(uuid.uuid4())[:8].upper()
    active_games[room_id] = generate_game_state()
    
    # Ссылка на фронтенд с параметром комнаты
    game_url = f"{FRONTEND_URL}?room={room_id}"
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎮 Открыть игровое поле", url=game_url)
    ]])
    
    await update.message.reply_text(
        f"✅ Комната создана!\n"
        f"ID: `{room_id}`\n"
        f"Отправьте этот ID друзьям для команды /join\n\n"
        f"Нажмите кнопку ниже, чтобы начать:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    logger.info(f"Создана комната: {room_id}")

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /join"""
    if not context.args:
        await update.message.reply_text("Укажите ID комнаты: /join ABC123")
        return
    
    room_id = context.args[0].upper()
    if room_id not in active_games:
        await update.message.reply_text("❌ Комната не найдена!")
        return
    
    game_url = f"{FRONTEND_URL}?room={room_id}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎮 Присоединиться к игре", url=game_url)
    ]])
    
    await update.message.reply_text(
        f"Вы присоединились к комнате `{room_id}`!\nНажмите кнопку:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# --- WebSocket сервер ---
async def websocket_handler(request):
    """Обработчик WebSocket соединений"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    room_id = request.query.get('room', '').upper()
    if not room_id or room_id not in active_games:
        await ws.close(code=1008, message=b'Invalid room')
        return ws
    
    # Регистрация соединения
    if room_id not in ws_connections:
        ws_connections[room_id] = []
    ws_connections[room_id].append(ws)
    
    try:
        # Отправляем текущее состояние
        await ws.send_json({
            'type': 'state_update',
            'game': active_games[room_id]
        })
        
        # Обработка сообщений
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await handle_game_action(room_id, data, ws)
                except json.JSONDecodeError:
                    pass
                    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Удаляем соединение при отключении
        if room_id in ws_connections and ws in ws_connections[room_id]:
            ws_connections[room_id].remove(ws)
            if not ws_connections[room_id]:
                del ws_connections[room_id]
    
    return ws

async def handle_game_action(room_id, data, ws):
    """Обработка игровых действий"""
    game = active_games.get(room_id)
    if not game:
        return
    
    action = data.get('action')
    
    if action == 'reveal':
        index = data.get('index')
        if index is None or not 0 <= index < 25:
            return
        
        if not game['revealed'][index]:
            game['revealed'][index] = True
            color = game['key'][index]
            
            # Рассылаем обновление всем игрокам
            await broadcast(room_id, {
                'type': 'card_revealed',
                'index': index,
                'color': color,
                'current_team': game['current_team']
            })
            
            # Проверяем условия конца игры
            await check_game_over(room_id, color)
    
    elif action == 'hint':
        # Логика для подсказки (упрощённая версия)
        game['hint'] = data.get('hint')
        game['hint_number'] = data.get('number')
        game['guesses_left'] = game['hint_number'] + 1
        game['status'] = 'guessing'
        
        await broadcast(room_id, {
            'type': 'hint_given',
            'hint': game['hint'],
            'number': game['hint_number'],
            'team': game['current_team']
        })

async def broadcast(room_id, message):
    """Рассылка сообщения всем в комнате"""
    if room_id in ws_connections:
        for ws in ws_connections[room_id]:
            try:
                await ws.send_json(message)
            except:
                pass

async def check_game_over(room_id, last_color):
    """Проверка условий завершения игры"""
    game = active_games.get(room_id)
    if not game:
        return
    
    if last_color == 'black':
        # Попали на убийцу
        winner = 'blue' if game['current_team'] == 'red' else 'red'
        await broadcast(room_id, {
            'type': 'game_over',
            'winner': winner,
            'reason': 'assassin'
        })
        if room_id in active_games:
            del active_games[room_id]
    
    # Подсчёт оставшихся карт
    red_remaining = sum(1 for i, c in enumerate(game['key']) 
                       if c == 'red' and not game['revealed'][i])
    blue_remaining = sum(1 for i, c in enumerate(game['key']) 
                        if c == 'blue' and not game['revealed'][i])
    
    if red_remaining == 0:
        await broadcast(room_id, {
            'type': 'game_over',
            'winner': 'red',
            'reason': 'all_found'
        })
        if room_id in active_games:
            del active_games[room_id]
    elif blue_remaining == 0:
        await broadcast(room_id, {
            'type': 'game_over',
            'winner': 'blue',
            'reason': 'all_found'
        })
        if room_id in active_games:
            del active_games[room_id]

# --- Вебхук обработчик ---
async def handle_webhook(request):
    """Принимаем обновления от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.update_queue.put(update)
        return web.Response(text="OK", status=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text="Error", status=500)

# --- Инициализация бота ---
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("newgame", newgame_command))
app.add_handler(CommandHandler("join", join_command))

async def start_server():
    """Запуск сервера"""
    logger.info("Запуск сервера...")
    
    # Устанавливаем вебхук
    webhook_url = f"{RENDER_URL}/telegram"
    await app.bot.set_webhook(webhook_url)
    logger.info(f"Вебхук установлен: {webhook_url}")
    
    # Настройка aiohttp сервера
    aiohttp_app = web.Application()
    aiohttp_app.router.add_get('/ws', websocket_handler)
    aiohttp_app.router.add_post('/telegram', handle_webhook)
    
    # Статическая страница для проверки
    async def index(request):
        return web.Response(text="Codenames Bot работает! ✅")
    
    aiohttp_app.router.add_get('/', index)
    
    runner = web.AppRunner(aiohttp_app)
    await runner.setup()
    
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Сервер запущен на порту {port}")
    print(f"✅ Сервер запущен! Проверьте: {RENDER_URL}")
    print(f"🤖 Бот активен. Фронтенд: {FRONTEND_URL}")
    
    # Бесконечное ожидание
    await asyncio.Future()

# --- Точка входа ---
if __name__ == '__main__':
    # Проверка обязательных переменных
    required_vars = ['BOT_TOKEN', 'RENDER_URL', 'FRONTEND_URL']
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        print(f"❌ Ошибка: отсутствуют переменные окружения: {', '.join(missing)}")
        print("Добавьте их в настройках Render:")
        print("1. BOT_TOKEN - токен от @BotFather")
        print(f"2. RENDER_URL - ваш URL на Render (сейчас: {os.environ.get('RENDER_URL', 'не задан')})")
        print(f"3. FRONTEND_URL - ваш GitHub Pages (сейчас: {os.environ.get('FRONTEND_URL', 'не задан')})")
        exit(1)
    
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        logger.info("Сервер остановлен")