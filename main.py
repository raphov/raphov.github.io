#!/usr/bin/env python3
import os
import asyncio
import logging
from aiohttp import web
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from utils.config import BOT_TOKEN, RENDER_URL
from utils.links import make_game_link
from game.room import GameRoom, active_rooms   # хранилище в room.py
from telegram.commands import *
from telegram.callbacks import *
from websocket.handler import websocket_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Application.builder().token(BOT_TOKEN).build()

async def setup():
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
    asyncio.create_task(app.updater.start_polling())

async def telegram_webhook(request):
    data = await request.json()
    update = Update.de_json(data, app.bot)
    await app.update_queue.put(update)
    return web.Response(text="OK")

async def health(request):
    return web.Response(text=f"Codenames | Rooms: {len(active_rooms)}")

async def main():
    await setup()
    server = web.Application()
    server.router.add_get('/', health)
    server.router.add_post('/telegram', telegram_webhook)
    server.router.add_get('/ws', websocket_handler)

    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    logger.info(f"Server running on port {port}")
    await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())