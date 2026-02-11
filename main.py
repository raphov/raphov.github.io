#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Codenames Telegram Bot + WebSocket Server
Модульная версия
"""

import os
import asyncio
import logging
from aiohttp import web

# Импортируем модули
from utils.config import BOT_TOKEN, RENDER_URL, FRONTEND_URL
from utils.logger import setup_logger
from telegram.commands import (
    start_command, new_command, join_command,
    list_command, help_command, unknown_command
)
from telegram.callbacks import role_callback, join_callback
from websocket.handler import websocket_handler

# Глобальное хранилище комнат (доступно во всех модулях)
active_rooms = {}

# Настраиваем логирование
logger = setup_logger()

async def telegram_webhook_handler(request):
    """Обработчик входящих обновлений от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        
        # Передаём обновление в очередь обработки
        await app.update_queue.put(update)
        
        return web.Response(text="OK", status=200)
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text="Error", status=500)

async def health_check(request):
    """Проверка работоспособности сервера"""
    return web.Response(text=f"Codenames Server\nActive rooms: {len(active_rooms)}\nVersion: 3.0 (Modular)")

async def cleanup_old_rooms():
    """Периодическая очистка старых комнат"""
    while True:
        await asyncio.sleep(300)  # Каждые 5 минут
        
        rooms_to_remove = []
        for room_id, room in active_rooms.items():
            if not room.is_active():
                rooms_to_remove.append(room_id)
        
        for room_id in rooms_to_remove:
            room = active_rooms[room_id]
            room.cleanup()
            del active_rooms[room_id]
            logger.info(f"Удалена устаревшая комната {room_id}")
        
        if rooms_to_remove:
            logger.info(f"Очищено {len(rooms_to_remove)} устаревших комнат")

async def main():
    """Основная функция запуска"""
    logger.info("="*70)
    logger.info("🚀 ЗАПУСК CODENAMES СЕРВЕРА v3.0 (MODULAR)")
    logger.info("="*70)
    
    # Инициализируем приложение Telegram
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
    from telegram import Bot
    
    global app
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("join", join_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Регистрируем обработчики callback-запросов
    app.add_handler(CallbackQueryHandler(role_callback, pattern="^role_"))
    app.add_handler(CallbackQueryHandler(join_callback, pattern="^join_"))
    
    # Обработчик неизвестных команд
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # Инициализируем приложение
    await app.initialize()
    await app.start()
    
    # Запускаем polling
    asyncio.create_task(app.updater.start_polling())
    
    # Настраиваем HTTP сервер
    server = web.Application()
    
    # Регистрируем маршруты
    server.router.add_get('/', health_check)
    server.router.add_post('/telegram', telegram_webhook_handler)
    server.router.add_get('/ws', websocket_handler)
    
    # Запускаем очистку старых комнат
    asyncio.create_task(cleanup_old_rooms())
    
    # Запускаем сервер
    runner = web.AppRunner(server)
    await runner.setup()
    
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"✅ СЕРВЕР ЗАПУЩЕН НА ПОРТУ {port}")
    logger.info(f"🌐 WebSocket: wss://{RENDER_URL.replace('https://', '')}/ws")
    logger.info(f"🎮 Фронтенд: {FRONTEND_URL}")
    logger.info("="*70)
    
    print("\n" + "="*70)
    print("✅ ВСЁ ГОТОВО! Сервер запущен и работает.")
    print("="*70 + "\n")
    
    # Бесконечное ожидание
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