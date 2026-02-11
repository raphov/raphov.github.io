// ==================== ГЛАВНЫЙ ФАЙЛ ====================

/**
 * Инициализация приложения
 */
function initApp() {
    console.log('🎮 Codenames Online v' + CONFIG.VERSION);
    
    // Получаем параметры URL
    var params = getUrlParams();
    roomId = params.roomId;
    role = params.role;
    
    console.log('📦 Комната:', roomId, 'Роль:', role);
    
    // Проверяем наличие комнаты
    if (!roomId) {
        UI.showError(
            '❌ Ошибка: нет кода комнаты',
            'Пожалуйста, откройте игру через ссылку от бота<br>' +
            '<a href="https://t.me/codenames_raphov_bot" target="_blank" style="color:#60a5fa;text-decoration:underline;">Перейти к боту</a>'
        );
        return;
    }
    
    // Сохраняем в localStorage
    localStorage.setItem('last_room', roomId);
    localStorage.setItem('last_role', role);
    
    // Отображаем ID комнаты
    if (UI.elements.roomDisplay) {
        UI.elements.roomDisplay.textContent = roomId;
    }
    
    // Обновляем список игроков
    UI.updatePlayersList(1);
    
    // Инициализируем менеджеры
    mobileManager.init();
    eventManager.init();
    
    // Настраиваем WebSocket обработчики
    setupWebSocketHandlers();
    
    // Подключаемся к серверу
    wsManager.connect(roomId, role);
}

/**
 * Настройка WebSocket обработчиков
 */
function setupWebSocketHandlers() {
    // Состояние подключения
    wsManager.on('connected', function() {
        UI.updateConnectionStatus('✅ Подключено к игровому серверу', 'connected');
        showNotification('Соединение установлено', 'success');
    });
    
    wsManager.on('disconnected', function() {
        UI.updateConnectionStatus('❌ Соединение прервано', 'error');
    });
    
    wsManager.on('reconnecting', function(data) {
        UI.updateConnectionStatus('🔄 Переподключение (' + data.attempt + '/' + CONFIG.MAX_RECONNECT_ATTEMPTS + ')...', 'connecting');
    });
    
    wsManager.on('reconnect_failed', function() {
        UI.updateConnectionStatus('❌ Не удалось подключиться. Обновите страницу.', 'error');
        showNotification('Не удалось подключиться к серверу', 'error');
    });
    
    // Инициализация игры
    wsManager.on('init', function(data) {
        gameManager.renderBoard(data.game_state);
        gameManager.updateGameInfo(data.game_state);
        UI.elements.gameArea.style.display = 'block';
        
        // Обновляем заголовок с ролью
        if (UI.elements.roomDisplay) {
            var roleText = (data.game_state.role === 'captain') ? '👑 Капитан' : '🔎 Агент';
            UI.elements.roomDisplay.textContent = roomId + ' - ' + roleText;
        }
    });
    
    wsManager.on('state_update', function(data) {
        gameManager.renderBoard(data.game_state);
        gameManager.updateGameInfo(data.game_state);
    });
    
    // Открытие карточки
    wsManager.on('card_revealed', function(data) {
        gameManager.updateCard(data.index, data.color);
    });
    
    // Смена хода
    wsManager.on('turn_switch', function(data) {
        if (gameManager.gameState) {
            gameManager.gameState.current_team = data.current_team;
            gameManager.updateGameInfo(gameManager.gameState);
            showNotification('Ход переходит к ' + TEAM_NAMES[data.current_team], 'info');
        }
    });
    
    // Конец игры
    wsManager.on('game_over', function(data) {
        gameManager.showGameOver(data.winner, 'Игра завершена!');
    });
    // Сброс игры
    wsManager.on('game_reset', function(data) {
        gameManager.renderBoard(data.game_state);
        gameManager.updateGameInfo(data.game_state);
        gameManager.currentMove = 1;
        showNotification('🔄 Новая игра началась!', 'success');
    });
        
    // Ошибки
    wsManager.on('error', function(data) {
        showNotification(data.message || 'Ошибка сервера', 'error');
    });
}

/**
 * Глобальная функция для уведомлений
 */
function showNotification(message, type, duration) {
    UI.showNotification(message, type, duration);
}

/**
 * Глобальная функция для обновления статуса
 */
function updateStatus(text, type) {
    UI.updateConnectionStatus(text, type);
}

/**
 * Глобальная функция для ошибок
 */
function showError(title, message) {
    UI.showError(title, message);
}

// Запускаем при загрузке страницы
document.addEventListener('DOMContentLoaded', initApp);

console.log('✅ Все модули загружены');
console.log('📱 Режим:', mobileManager.isMobile ? 'Мобильный' : 'Десктоп');
console.log('🔄 Ориентация:', mobileManager.orientation);