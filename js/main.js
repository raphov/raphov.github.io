// ==================== ГЛАВНЫЙ ФАЙЛ ====================

/**
 * Инициализация приложения
 */
async function initApp() {
    console.log(`🎮 Codenames Online v${CONFIG.VERSION}`);
    console.log('📱 Режим:', mobileManager.isMobile ? 'Мобильный' : 'Десктоп');
    
    // Получаем параметры URL
    const { roomId, userId } = getUrlParams();

    if (!roomId) { ... }
    if (!userId) {
        UI.showError(
            '❌ Ошибка: нет ID пользователя',
            'Пожалуйста, откройте игру через ссылку из Telegram-бота.<br>' +
            'Вы должны сначала выбрать роль в боте.'
        );
        return;
    }
    // Сохраняем в localStorage
    localStorage.setItem('last_room', roomId);
    localStorage.setItem('last_user', userId);
    
    // Отображаем ID комнаты
    if (UI.elements.roomDisplay) {
        UI.elements.roomDisplay.textContent = roomId;
    }
    
    // Инициализируем менеджеры
    mobileManager.init();
    eventManager.init();
    
    // Настраиваем WebSocket обработчики
    setupWebSocketHandlers();
    
    // Подключаемся к серверу
    wsManager.connect(roomId, userId);
}

/**
 * Настройка WebSocket обработчиков
 */
function setupWebSocketHandlers() {
    // Состояние подключения
    wsManager.on('connected', () => {
        UI.updateConnectionStatus('✅ Подключено к игровому серверу', 'connected');
        UI.showNotification('Соединение установлено', 'success');
    });
    
    wsManager.on('disconnected', () => {
        UI.updateConnectionStatus('❌ Соединение прервано', 'error');
    });
    
    wsManager.on('reconnecting', (data) => {
        UI.updateConnectionStatus(`🔄 Переподключение (${data.attempt}/${CONFIG.MAX_RECONNECT_ATTEMPTS})...`, 'connecting');
    });
    
    wsManager.on('reconnect_failed', () => {
        UI.updateConnectionStatus('❌ Не удалось подключиться. Обновите страницу.', 'error');
        UI.showNotification('Не удалось подключиться к серверу', 'error');
    });
    
    // Инициализация игры
    wsManager.on('init', (data) => {
        gameManager.renderBoard(data.game_state);
        gameManager.updateGameInfo(data.game_state);
        UI.elements.gameArea.style.display = 'block';
    });
    
    wsManager.on('state_update', (data) => {
        gameManager.renderBoard(data.game_state);
        gameManager.updateGameInfo(data.game_state);
    });
    
    // Открытие карточки
    wsManager.on('card_revealed', (data) => {
        gameManager.updateCard(data.index, data.color);
    });
    
    // Смена хода
    wsManager.on('turn_switch', (data) => {
        if (gameManager.gameState) {
            gameManager.gameState.current_team = data.current_team;
            gameManager.updateGameInfo(gameManager.gameState);
            UI.showNotification(
                `Ход переходит к ${TEAM_NAMES[data.current_team]}`,
                'info'
            );
        }
    });
    
    // Игрок подключился
    wsManager.on('player_joined', (data) => {
        UI.updatePlayersList(data.players_count);
        UI.showNotification(`👤 Новый игрок! Всего: ${data.players_count}`, 'info');
    });
    
    // Игрок отключился
    wsManager.on('player_left', (data) => {
        UI.updatePlayersList(data.players_count);
        UI.showNotification(`👤 Игрок вышел. Всего: ${data.players_count}`, 'warning');
    });
    
    // Конец игры
    wsManager.on('game_over', (data) => {
        gameManager.showGameOver(data.winner, 'Игра завершена!');
    });
    
    // Ошибки
    wsManager.on('error', (data) => {
        UI.showNotification(data.message || 'Ошибка сервера', 'error');
    });
}

// Запускаем при загрузке страницы
document.addEventListener('DOMContentLoaded', initApp);

// ==================== ДЕБАГ ИНФОРМАЦИЯ ====================
console.log(`
╔══════════════════════════════════════════╗
║      CODENAMES ONLINE v${CONFIG.VERSION} MODULAR      ║
║   Разделено на модули для удобства        ║
╚══════════════════════════════════════════╝

📦 Модули загружены:
• config.js    - Конфигурация
• utils.js     - Утилиты
• websocket.js - WebSocket менеджер
• game.js      - Логика игры
• ui.js        - Интерфейс
• mobile.js    - Мобильная оптимизация
• events.js    - События
• main.js      - Главный

🎮 Режим: ${mobileManager.isMobile ? 'Мобильный' : 'Десктоп'}
🔄 Ориентация: ${mobileManager.orientation}
`);