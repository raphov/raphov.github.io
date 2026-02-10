import os, json, uuid, random, asyncio, logging
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Настройка логирования ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.basicConfig(level=logging.DEBUG) # Добавьте эту строку
logger = logging.getLogger(__name__)

# --- Конфигурация ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
RENDER_URL = os.environ.get('RENDER_URL')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://ваш-ник.github.io')  # Убедитесь, что это ваш URL
WEBHOOK_PATH = '/telegram'
WS_PATH = '/ws'

# --- Глобальные хранилища ---
active_games = {}       # room_id -> game_data
ws_rooms = {}           # room_id -> [websocket1, websocket2, ...]

# --- Игровая логика ---
def create_game():
    words = random.sample([
        "яблоко", "гора", "мост", "врач", "луна", "книга", "огонь", "река", "часы",
        "снег", "глаз", "дом", "змея", "кольцо", "корабль", "лев", "лес", "машина",
        "медведь", "нос", "океан", "перо", "пила", "поле", "пуля"
    ], 25)
    
    colors = (['red'] * 9) + (['blue'] * 8) + ['black'] + (['neutral'] * 7)
    random.shuffle(colors)
    
    return {
        'words': words,
        'colors': colors,
        'opened': [False] * 25,
        'current_team': 'red',
        'hint': None,
        'hint_num': None,
        'guesses_left': 0,
        'created_at': asyncio.get_event_loop().time()
    }

# --- Telegram команды ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 **Codenames Bot**\n\n"
        "Создать комнату: /new\n"
        "Присоединиться: /join <код>\n\n"
        "Бот работает в связке с веб-интерфейсом.",
        parse_mode='Markdown'
    )

async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room_id = str(uuid.uuid4())[:6].upper()
    active_games[room_id] = create_game()
    ws_rooms[room_id] = []
    
    game_url = f"{FRONTEND_URL}?room={room_id}"
    button = InlineKeyboardButton("▶️ Открыть игровой стол", url=game_url)
    
    await update.message.reply_text(
        f"✅ **Комната создана!**\n\n"
        f"**Код:** `{room_id}`\n"
        f"**Ссылка:** {game_url}\n\n"
        f"1. Отправьте код друзьям для /join\n"
        f"2. Нажмите кнопку ниже чтобы открыть игровой стол",
        reply_markup=InlineKeyboardMarkup([[button]]),
        parse_mode='Markdown'
    )
    logger.info(f"Создана комната {room_id}")

async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Укажите код комнаты: /join ABC123")
        return
    
    room_id = context.args[0].upper()
    if room_id not in active_games:
        await update.message.reply_text("❌ Комната не найдена или устарела.")
        return
    
    game_url = f"{FRONTEND_URL}?room={room_id}"
    button = InlineKeyboardButton("🎮 Присоединиться к игре", url=game_url)
    
    await update.message.reply_text(
        f"🔗 **Присоединение к комнате {room_id}**\n\n"
        f"Нажмите кнопку ниже:",
        reply_markup=InlineKeyboardMarkup([[button]]),
        parse_mode='Markdown'
    )

# --- WebSocket сервер ---
async def websocket_handler(request):
    ws = web.WebSocketResponse(autoping=True, heartbeat=30)
    await ws.prepare(request)
    
    room_id = request.query.get('room', '').upper()
    client_ip = request.remote
    
    if not room_id:
        logger.warning(f"{client_ip}: Отсутствует room_id")
        await ws.close(code=1008, message=b'Room ID required')
        return ws
    
    if room_id not in active_games:
        logger.warning(f"{client_ip}: Комната {room_id} не найдена")
        await ws.close(code=1008, message=b'Room not found')
        return ws
    
    # Регистрируем соединение
    ws_rooms[room_id].append(ws)
    logger.info(f"{client_ip}: Подключен к комнате {room_id} (всего: {len(ws_rooms[room_id])})")
    
    try:
        # Отправляем текущее состояние новому игроку
        game_state = active_games[room_id]
        await ws.send_json({
            'type': 'init',
            'room': room_id,
            'words': game_state['words'],
            'colors': game_state['colors'],
            'opened': game_state['opened'],
            'current_team': game_state['current_team']
        })
        
        # Оповещаем остальных о новом игроке
        for other_ws in ws_rooms[room_id]:
            if other_ws != ws and not other_ws.closed:
                await other_ws.send_json({
                    'type': 'player_joined',
                    'count': len(ws_rooms[room_id])
                })
        
        # Обработка сообщений от клиента
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await handle_client_message(room_id, data, ws)
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка JSON: {e}")
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket ошибка: {ws.exception()}")
                break
                
    except Exception as e:
        logger.error(f"Ошибка в обработчике WS: {e}")
    finally:
        # Удаляем соединение при отключении
        if room_id in ws_rooms and ws in ws_rooms[room_id]:
            ws_rooms[room_id].remove(ws)
            logger.info(f"{client_ip}: Отключен от комнаты {room_id}")
            
            # Если комната пуста более 5 минут - очищаем
            if not ws_rooms[room_id]:
                del ws_rooms[room_id]
                logger.info(f"Комната {room_id} удалена (нет подключений)")
    
    return ws

async def handle_client_message(room_id, data, ws):
    """Обработка сообщений от игроков"""
    action = data.get('action')
    game = active_games.get(room_id)
    
    if not game:
        return
    
    if action == 'click_card':
        idx = data.get('index')
        if idx is None or not 0 <= idx < 25:
            return
        
        if game['opened'][idx]:
            return  # Уже открыта
        
        game['opened'][idx] = True
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
        
        # Проверяем победу
        await check_victory(room_id, color)
        
    elif action == 'ping':
        await ws.send_json({'type': 'pong', 'time': asyncio.get_event_loop().time()})

async def check_victory(room_id, last_color):
    """Упрощённая проверка условий победы"""
    game = active_games.get(room_id)
    if not game:
        return
    
    if last_color == 'black':
        winner = 'blue' if game['current_team'] == 'red' else 'red'
        await broadcast(room_id, {'type': 'game_over', 'winner': winner, 'reason': 'Убийца!'})
        return
    
    red_left = sum(1 for i, c in enumerate(game['colors']) 
                   if c == 'red' and not game['opened'][i])
    blue_left = sum(1 for i, c in enumerate(game['colors']) 
                    if c == 'blue' and not game['opened'][i])
    
    if red_left == 0:
        await broadcast(room_id, {'type': 'game_over', 'winner': 'red', 'reason': 'Все агенты!'})
    elif blue_left == 0:
        await broadcast(room_id, {'type': 'game_over', 'winner': 'blue', 'reason': 'Все агенты!'})

async def broadcast(room_id, message):
    """Рассылка сообщения всем в комнате"""
    for client in ws_rooms.get(room_id, []):
        if not client.closed:
            try:
                await client.send_json(message)
            except:
                pass

# --- Вебхук обработчик ---
async def webhook_handler(request):
    """Принимаем обновления от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.update_queue.put(update)
        return web.Response(text="OK", status=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text="Error", status=500)

async def health_check(request):
    """Для проверки работоспособности Render"""
    return web.Response(text="Codenames Server is running")

# --- Инициализация ---
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", cmd_start))
app.add_handler(CommandHandler("new", cmd_new))
app.add_handler(CommandHandler("join", cmd_join))

async def main():
    logger.info("Запуск Codenames сервера...")
    
    # Проверка переменных
    if not BOT_TOKEN or not RENDER_URL:
        logger.error("❌ Отсутствуют BOT_TOKEN или RENDER_URL")
        return
    
    # Установка вебхука
    await app.bot.set_webhook(f"{RENDER_URL}{WEBHOOK_PATH}")
    logger.info(f"Вебхук установлен: {RENDER_URL}{WEBHOOK_PATH}")
    
    # Настройка HTTP сервера
    server = web.Application()
    server.router.add_get(WS_PATH, websocket_handler)
    server.router.add_post(WEBHOOK_PATH, webhook_handler)
    server.router.add_get('/', health_check)
    
    runner = web.AppRunner(server)
    await runner.setup()
    
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"✅ Сервер запущен на порту {port}")
    logger.info(f"   WebSocket: wss://ваш-проект.onrender.com{WS_PATH}")
    logger.info(f"   Webhook: {RENDER_URL}{WEBHOOK_PATH}")
    logger.info(f"   Фронтенд: {FRONTEND_URL}")
    
    # Бесконечная работа
    await asyncio.Future()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Сервер остановлен")