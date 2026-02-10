import os, json, uuid, random, asyncio, logging
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Конфигурация (ЗАПОЛНИТЕ ЭТИ ПЕРЕМЕННЫЕ В RENDER!) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
RENDER_URL = os.environ.get('RENDER_URL', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://raphov.github.io')

# --- Проверка обязательных переменных ---
if not BOT_TOKEN:
    logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не задан!")
    print("\n" + "="*60)
    print("ДОБАВЬТЕ В НАСТРОЙКАХ RENDER:")
    print("BOT_TOKEN = ваш_токен_от_BotFather")
    print("RENDER_URL = https://ваш-проект.onrender.com")
    print("FRONTEND_URL = https://raphov.github.io")
    print("="*60 + "\n")
    exit(1)

if not RENDER_URL:
    RENDER_URL = "https://codenames-u88n.onrender.com"
    logger.warning(f"⚠️  RENDER_URL не задан, использую по умолчанию: {RENDER_URL}")

# --- Глобальные хранилища ---
active_games = {}    # room_id -> game_data
ws_rooms = {}        # room_id -> [websocket1, websocket2, ...]

# --- Список слов для игры ---
WORDS = [
    "яблоко", "гора", "мост", "врач", "луна", "книга", "огонь", "река", "часы",
    "снег", "глаз", "дом", "змея", "кольцо", "корабль", "лев", "лес", "машина",
    "медведь", "нос", "океан", "перо", "пила", "поле", "пуля", "работа", "роза",
    "рука", "сапог", "сок", "стол", "театр", "тень", "фонтан", "хлеб", "школа",
    "шляпа", "ящик", "игла", "йогурт", "зонт", "ксерокс", "эхо", "юла", "якорь"
]

def create_game():
    """Создаёт новую игру со случайными словами и раскладкой"""
    words = random.sample(WORDS, 25)
    
    # Распределение карточек: 9 красных, 8 синих, 1 чёрный (убийца), 7 нейтральных
    colors = (['red'] * 9) + (['blue'] * 8) + ['black'] + (['neutral'] * 7)
    random.shuffle(colors)
    
    return {
        'words': words,
        'colors': colors,
        'revealed': [False] * 25,
        'current_team': 'red',
        'status': 'waiting',
        'players': []
    }

# ==================== КОМАНДЫ TELEGRAM ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.username}) вызвал /start")
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "🎮 **Добро пожаловать в Codenames!**\n\n"
        "Создать новую комнату: /new\n"
        "Присоединиться к существующей: /join <код_комнаты>\n\n"
        "Пример: `/join ABC123`",
        parse_mode='Markdown'
    )

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /new - создаёт комнату"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} вызвал /new")
    
    # Генерируем уникальный код комнаты
    room_id = str(uuid.uuid4())[:6].upper()
    
    # Создаём и сохраняем игру
    active_games[room_id] = create_game()
    ws_rooms[room_id] = []  # Пока нет WebSocket-подключений
    
    # Формируем ссылку на фронтенд с параметром комнаты
    game_url = f"{FRONTEND_URL}?room={room_id}"
    
    # Создаём кнопку для открытия игры
    button = InlineKeyboardButton("▶️ Открыть игровой стол", url=game_url)
    
    # Отправляем сообщение с кнопкой
    message = await update.message.reply_text(
        f"✅ **Игровая комната создана!**\n\n"
        f"**Код комнаты:** `{room_id}`\n"
        f"**Ссылка для игроков:** {game_url}\n\n"
        f"1. Отправьте код `{room_id}` друзьям\n"
        f"2. Нажмите кнопку ниже, чтобы открыть игровое поле",
        reply_markup=InlineKeyboardMarkup([[button]]),
        parse_mode='Markdown'
    )
    
    logger.info(f"Создана комната: {room_id}. Сообщение ID: {message.message_id}")

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /join - присоединение к комнате"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} вызвал /join с аргументами: {context.args}")
    
    if not context.args:
        await update.message.reply_text("❌ Укажите код комнаты: `/join ABC123`", parse_mode='Markdown')
        return
    
    room_id = context.args[0].upper()
    
    if room_id not in active_games:
        await update.message.reply_text("❌ Комната не найдена. Возможно, она устарела.")
        return
    
    # Формируем ту же ссылку, что и при создании
    game_url = f"{FRONTEND_URL}?room={room_id}"
    button = InlineKeyboardButton("🎮 Присоединиться к игре", url=game_url)
    
    await update.message.reply_text(
        f"🔗 **Присоединение к комнате {room_id}**\n\n"
        f"Нажмите кнопку ниже, чтобы открыть игровое поле:",
        reply_markup=InlineKeyboardMarkup([[button]]),
        parse_mode='Markdown'
    )

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных команд"""
    await update.message.reply_text(
        "🤔 Неизвестная команда.\n"
        "Доступные команды: /start, /new, /join"
    )

# ==================== WEBHOOK ОБРАБОТЧИК ====================
async def telegram_webhook_handler(request):
    """Принимает обновления от Telegram API"""
    logger.info(f"Получен запрос на вебхук от {request.remote}")
    
    try:
        # Парсим JSON из запроса
        data = await request.json()
        logger.info(f"Данные вебхука: {json.dumps(data, ensure_ascii=False)[:200]}...")
        
        # Преобразуем в объект Update
        update = Update.de_json(data, app.bot)
        
        # Передаём обновление в очередь обработки
        await app.update_queue.put(update)
        
        # Отвечаем Telegram, что всё получили
        logger.info(f"Вебхук успешно обработан")
        return web.Response(text="OK", status=200)
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return web.Response(text="Bad Request", status=400)
    except Exception as e:
        logger.error(f"Ошибка в обработчике вебхука: {e}")
        return web.Response(text="Error", status=500)

# ==================== WEBSOCKET СЕРВЕР ====================
async def websocket_handler(request):
    """Обработчик WebSocket соединений от фронтенда"""
    ws = web.WebSocketResponse(autoping=True, heartbeat=30)
    await ws.prepare(request)
    
    # Получаем код комнаты из параметров запроса
    room_id = request.query.get('room', '').upper()
    client_ip = request.remote
    
    logger.info(f"WebSocket подключение от {client_ip}, комната: '{room_id}'")
    
    if not room_id or room_id == 'NULL' or room_id == 'NULL':
        logger.warning(f"{client_ip}: Отсутствует код комнаты")
        await ws.close(code=1008, message=b'Room ID required')
        return ws
    
    if room_id not in active_games:
        logger.warning(f"{client_ip}: Комната {room_id} не найдена")
        await ws.close(code=1008, message=b'Room not found')
        return ws
    
    # Регистрируем новое соединение
    if room_id not in ws_rooms:
        ws_rooms[room_id] = []
    ws_rooms[room_id].append(ws)
    
    logger.info(f"{client_ip}: Подключён к комнате {room_id} (всего: {len(ws_rooms[room_id])})")
    
    try:
        # Отправляем текущее состояние игры новому игроку
        game_state = active_games[room_id]
        await ws.send_json({
            'type': 'init',
            'room': room_id,
            'words': game_state['words'],
            'colors': game_state['colors'],
            'revealed': game_state['revealed'],
            'current_team': game_state['current_team']
        })
        
        # Оповещаем остальных игроков о новом участнике
        for other_ws in ws_rooms[room_id]:
            if other_ws != ws and not other_ws.closed:
                await other_ws.send_json({
                    'type': 'player_joined',
                    'count': len(ws_rooms[room_id])
                })
        
        # Обрабатываем сообщения от клиента
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                logger.debug(f"Получено сообщение от {client_ip}: {msg.data}")
                try:
                    data = json.loads(msg.data)
                    await handle_client_message(room_id, data, ws)
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка JSON: {e}")
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"Ошибка WebSocket: {ws.exception()}")
                
    except Exception as e:
        logger.error(f"Ошибка в обработчике WebSocket: {e}")
    finally:
        # Удаляем соединение при отключении
        if room_id in ws_rooms and ws in ws_rooms[room_id]:
            ws_rooms[room_id].remove(ws)
            logger.info(f"{client_ip}: Отключён от комнаты {room_id}")
            
            # Если комната пуста, можно её очистить через некоторое время
            if not ws_rooms[room_id]:
                logger.info(f"Комната {room_id} пуста")
    
    return ws

async def handle_client_message(room_id, data, ws):
    """Обработка сообщений от игроков"""
    action = data.get('action')
    game = active_games.get(room_id)
    
    if not game:
        return
    
    # Игрок кликнул на карточку
    if action == 'click_card':
        idx = data.get('index')
        if idx is None or not 0 <= idx < 25:
            return
        
        if game['revealed'][idx]:
            return  # Карточка уже открыта
        
        # Открываем карточку
        game['revealed'][idx] = True
        color = game['colors'][idx]
        
        # Рассылаем обновление всем в комнате
        for client in ws_rooms.get(room_id, []):
            if not client.closed:
                await client.send_json({
                    'type': 'card_opened',
                    'index': idx,
                    'color': color,
                    'current_team': game['current_team']
                })
        
        # Проверяем условия победы
        await check_game_over(room_id, color)
    
    # Пинг для поддержания соединения
    elif action == 'ping':
        await ws.send_json({'type': 'pong', 'time': asyncio.get_event_loop().time()})

async def check_game_over(room_id, last_color):
    """Проверка условий завершения игры"""
    game = active_games.get(room_id)
    if not game:
        return
    
    # Если открыли чёрную карточку (убийцу)
    if last_color == 'black':
        winner = 'blue' if game['current_team'] == 'red' else 'red'
        await broadcast(room_id, {
            'type': 'game_over',
            'winner': winner,
            'reason': 'Найден убийца!'
        })
        # Очищаем комнату
        if room_id in active_games:
            del active_games[room_id]
        if room_id in ws_rooms:
            del ws_rooms[room_id]
        return
    
    # Считаем оставшиеся карточки каждой команды
    red_remaining = sum(1 for i, c in enumerate(game['colors']) 
                       if c == 'red' and not game['revealed'][i])
    blue_remaining = sum(1 for i, c in enumerate(game['colors']) 
                        if c == 'blue' and not game['revealed'][i])
    
    # Если одна из команд открыла все свои карточки
    if red_remaining == 0:
        await broadcast(room_id, {
            'type': 'game_over',
            'winner': 'red',
            'reason': 'Все агенты найдены!'
        })
        if room_id in active_games:
            del active_games[room_id]
        if room_id in ws_rooms:
            del ws_rooms[room_id]
    elif blue_remaining == 0:
        await broadcast(room_id, {
            'type': 'game_over',
            'winner': 'blue',
            'reason': 'Все агенты найдены!'
        })
        if room_id in active_games:
            del active_games[room_id]
        if room_id in ws_rooms:
            del ws_rooms[room_id]

async def broadcast(room_id, message):
    """Рассылка сообщения всем в комнате"""
    for client in ws_rooms.get(room_id, []):
        if not client.closed:
            try:
                await client.send_json(message)
            except:
                pass

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def health_check(request):
    """Проверка работоспособности сервера"""
    return web.Response(text="✅ Codenames Server работает!")

async def list_rooms(request):
    """Список активных комнат (для отладки)"""
    rooms = []
    for room_id, game in active_games.items():
        players = len(ws_rooms.get(room_id, []))
        rooms.append({
            'room_id': room_id,
            'players': players,
            'words': game['words'][:3]  # первые 3 слова для примера
        })
    
    return web.json_response({
        'active_games': len(active_games),
        'rooms': rooms
    })

# ==================== ИНИЦИАЛИЗАЦИЯ И ЗАПУСК ====================
# Создаём приложение Telegram-бота
app = None

async def setup_application():
    """Настройка и запуск приложения"""
    global app
    
    # Инициализация приложения
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("join", join_command))
    
    # Обработчик неизвестных команд
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # Инициализируем приложение
    await app.initialize()
    
    # НЕ запускаем поллинг, используем вебхуки
    logger.info("✅ Приложение Telegram бота инициализировано")

async def main():
    """Основная функция запуска сервера"""
    logger.info("="*60)
    logger.info("🚀 ЗАПУСК CODENAMES СЕРВЕРА")
    logger.info("="*60)
    
    logger.info(f"BOT_TOKEN: {'установлен' if BOT_TOKEN else 'НЕТ!'}")
    logger.info(f"RENDER_URL: {RENDER_URL}")
    logger.info(f"FRONTEND_URL: {FRONTEND_URL}")
    
    try:
        # Устанавливаем вебхук
        bot = Bot(token=BOT_TOKEN)
        webhook_url = f"{RENDER_URL}/"
        
        logger.info(f"Устанавливаю вебхук на: {webhook_url}")
        await bot.set_webhook(webhook_url)
        logger.info("✅ Вебхук успешно установлен")
        
        # Получаем информацию о вебхуке для проверки
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Информация о вебхуке: {webhook_info.url}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при установке вебхука: {e}")
        raise
    
    # Настраиваем приложение Telegram
    await setup_application()
    
    # Настраиваем HTTP сервер
    server = web.Application()
    
    # Регистрируем маршруты:
    server.router.add_get('/', health_check)               # GET / для проверки
    server.router.add_post('/', telegram_webhook_handler)  # POST / для вебхука Telegram
    server.router.add_get('/ws', websocket_handler)        # WebSocket для игры
    server.router.add_get('/debug/rooms', list_rooms)      # Для отладки
    
    # Запускаем сервер
    runner = web.AppRunner(server)
    await runner.setup()
    
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info("="*60)
    logger.info(f"✅ СЕРВЕР ЗАПУЩЕН НА ПОРТУ {port}")
    logger.info(f"🌐 WebSocket: wss://{RENDER_URL.replace('https://', '')}/ws")
    logger.info(f"🤖 Webhook: {webhook_url}")
    logger.info(f"🎮 Фронтенд: {FRONTEND_URL}")
    logger.info("="*60)
    
    print("\n" + "="*60)
    print("✅ ВСЁ ГОТОВО! Сервер запущен и работает.")
    print("="*60)
    print(f"1. Проверьте вебхук: {webhook_url}")
    print(f"2. Напишите /new в Telegram боту")
    print(f"3. Нажмите кнопку от бота, чтобы открыть игру")
    print(f"4. Игра откроется по адресу: {FRONTEND_URL}")
    print("="*60 + "\n")
    
    # Бесконечная работа
    await asyncio.Future()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Сервер остановлен по запросу пользователя")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*60)
        print("ПРОВЕРЬТЕ ПЕРЕМЕННЫЕ В RENDER:")
        print(f"BOT_TOKEN = {'установлен' if BOT_TOKEN else 'НЕТ!'}")
        print(f"RENDER_URL = {RENDER_URL}")
        print("="*60 + "\n")