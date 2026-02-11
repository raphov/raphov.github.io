# utils/config.py
import os

# Конфигурация из переменных окружения (НЕ ХРАНИТЬ ТОКЕН В КОДЕ!)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
RENDER_URL = os.environ.get('RENDER_URL', 'https://codenames-u88n.onrender.com')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://raphov.github.io')

# Проверка наличия токена при запуске
if not BOT_TOKEN:
    print("\n" + "="*70)
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не задан!")
    print("="*70)
    print("Добавьте переменную окружения BOT_TOKEN в настройках Render:")
    print("1. Зайдите в Dashboard Render")
    print("2. Выберите ваш Web Service")
    print("3. Вкладка Environment")
    print("4. Добавьте переменную: Key = BOT_TOKEN, Value = ваш_токен_от_BotFather")
    print("5. Нажмите Save и перезапустите сервис")
    print("="*70 + "\n")
    # Не выходим, но будет ошибка при запуске