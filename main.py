#!/usr/bin/env python3
import os
import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Импорты из наших модулей
from utils.config import BOT_TOKEN, RENDER_URL
from game.room import active_rooms
from telegram.commands import *
from telegram.callbacks import *
from websocket.handler import websocket_handler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаём приложение Telegram
app = Application.builder().token(BOT_TOKEN).build()

async def setup_telegram():
    """Регистрация обработчиков команд"""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("join", join_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("help", help_command))
    
    app.add_handler(CallbackQueryHandler(role_callback, pattern="^role_"))
    app.add_handler(CallbackQueryHandler(join_callback, pattern="^join_"))
    
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    await app.initialize()
    await app.start()
    
    # Запускаем polling вместо webhook для разработки
    asyncio.create_task(app.updater.start_polling())
    logger.info("✅ Telegram бот запущен в режиме polling")

async def telegram_webhook_handler(request):
    """Обработчик вебхука от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.update_queue.put(update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text="Error", status=500)

async def health_check(request):
    """Проверка работоспособности"""
    return web.Response(
        text=f"Codenames Server v3.0\n"
             f"Active rooms: {len(active_rooms)}\n"
             f"BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}"
    )

async def cleanup_old_rooms():
    """Периодическая очистка старых комнат"""
    while True:
        await asyncio.sleep(300)  # 5 минут
        rooms_to_remove = []
        for room_id, room in list(active_rooms.items()):
            if not room.is_active():
                room.cleanup()
                rooms_to_remove.append(room_id)
        
        for room_id in rooms_to_remove:
            del active_rooms[room_id]
        
        if rooms_to_remove:
            logger.info(f"Очищено {len(rooms_to_remove)} старых комнат")

async def main():
    """Запуск сервера"""
    logger.info("="*70)
    logger.info("🚀 ЗАПУСК CODENAMES СЕРВЕРА v3.0")
    logger.info("="*70)
    
    # Проверка токена
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не задан! Сервер остановлен.")
        return
    
    logger.info(f"✅ BOT_TOKEN: найден")
    logger.info(f"🌐 RENDER_URL: {RENDER_URL}")
    logger.info(f"🎮 FRONTEND_URL: {FRONTEND_URL}")
    
    # Запускаем Telegram бота
    await setup_telegram()
    
    # Создаём HTTP сервер
    server = web.Application()
    server.router.add_get('/', health_check)
    server.router.add_post('/telegram', telegram_webhook_handler)
    server.router.add_get('/ws', websocket_handler)
    
    # Запускаем сервер
    runner = web.AppRunner(server)
    await runner.setup()
    
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # Запускаем очистку комнат
    asyncio.create_task(cleanup_old_rooms())
    
    logger.info(f"✅ HTTP сервер запущен на порту {port}")
    logger.info("="*70)
    logger.info("🎮 Сервер готов к работе!")
    logger.info("="*70)
    
    # Бесконечное ожидание
    await asyncio.Future()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Сервер остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()