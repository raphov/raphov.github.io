// ==================== КОНФИГУРАЦИЯ ====================
const RENDER_URL = 'codenames-u88n.onrender.com'; // Ваш домен Render
const HOLD_DURATION = 2000; // 2 секунды удержания
const VERSION = '1.1.0';

// ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================
let roomId = null;
let socket = null;
let gameData = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
let holdTimers = {};
let soundEnabled = true;
let currentMove = 1;
let isFullscreen = false;

// Элементы интерфейса
const elements = {
    roomDisplay: document.getElementById('roomDisplay'),
    connectionStatus: document.getElementById('connectionStatus'),
    gameBoard: document.getElementById('gameBoard'),
    playerCount: document.getElementById('playerCount'),
    redCount: document.getElementById('redCount'),
    blueCount: document.getElementById('blueCount'),
    currentTurn: document.getElementById('currentTurn'),
    openedCards: document.getElementById('openedCards'),
    currentMove: document.getElementById('currentMove'),
    playersList: document.getElementById('playersList'),
    gameArea: document.getElementById('gameArea'),
    notification: document.getElementById('notification'),
    rulesModal: document.getElementById('rulesModal'),
    burgerBtn: document.getElementById('burgerBtn'),
    menuContent: document.getElementById('menuContent'),
    menuOverlay: document.getElementById('menuOverlay'),
    closeMenu: document.getElementById('closeMenu'),
    btnFullscreen: document.getElementById('btnFullscreen')
};

// ==================== ИНИЦИАЛИЗАЦИЯ ====================
document.addEventListener('DOMContentLoaded', () => {
    console.log(`🎮 Codenames Online v${VERSION}`);
    
    initializeRoom();
    setupEventListeners();
    optimizeForMobile();
    setupOrientationControls();
    connectWebSocket();
});

// ==================== ПОЛУЧЕНИЕ ID КОМНАТЫ ====================
function initializeRoom() {
    const urlParams = new URLSearchParams(window.location.search);
    roomId = urlParams.get('room');
    
    if (!roomId) {
        showError('❌ Ошибка: нет кода комнаты', 
            'Пожалуйста, откройте игру через кнопку в Telegram-боте<br>' +
            '<a href="https://t.me/codenames_raphov_bot" target="_blank" style="color:#60a5fa;text-decoration:underline;">Перейти к боту</a>');
        elements.roomDisplay.textContent = 'НЕТ КОДА';
        return;
    }
    
    roomId = roomId.toUpperCase();
    localStorage.setItem('last_room', roomId);
    elements.roomDisplay.textContent = roomId;
    
    console.log(`📦 Комната: ${roomId}`);
    console.log(`🌐 Render URL: ${RENDER_URL}`);
}

// ==================== НАСТРОЙКА ВСЕХ ОБРАБОТЧИКОВ СОБЫТИЙ ====================
function setupEventListeners() {
    // Копирование ссылки
    document.getElementById('btnCopyLink').addEventListener('click', copyRoomLink);
    
    // Новая игра
    document.getElementById('btnNewGame').addEventListener('click', () => {
        if (confirm('Создать новую игру? Текущий прогресс будет потерян.')) {
            location.reload();
        }
    });
    
    // Бургер-меню
    elements.burgerBtn.addEventListener('click', toggleMenu);
    elements.menuOverlay.addEventListener('click', closeMenu);
    elements.closeMenu.addEventListener('click', closeMenu);
    
    // Кнопки меню
    document.getElementById('showRules').addEventListener('click', showRules);
    document.getElementById('changeRole').addEventListener('click', () => {
        showNotification('Используйте команду /key в боте', 'info');
    });
    
    document.getElementById('requestKey').addEventListener('click', () => {
        if (roomId) {
            navigator.clipboard.writeText(`/key ${roomId}`);
            showNotification('Команда скопирована! Отправьте её боту', 'success');
            closeMenu();
        }
    });
    
    document.getElementById('soundToggle').addEventListener('click', toggleSound);
    
    // Модальное окно с правилами
    document.querySelector('.modal-close').addEventListener('click', () => {
        elements.rulesModal.classList.remove('show');
    });
    
    // Закрытие модального окна при клике на фон
    elements.rulesModal.addEventListener('click', (e) => {
        if (e.target === elements.rulesModal) {
            elements.rulesModal.classList.remove('show');
        }
    });
    
    // Полноэкранный режим
    elements.btnFullscreen.addEventListener('click', toggleFullscreen);
    
    // Выход из полноэкранного режима по клавише ESC
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    
    // Горячие клавиши
    document.addEventListener('keydown', handleHotkeys);
    
    // Изменение ориентации экрана
    window.addEventListener('orientationchange', handleOrientationChange);
    window.addEventListener('resize', updateGameLayout);
}

// ==================== УПРАВЛЕНИЕ ОРИЕНТАЦИЕЙ ====================
function setupOrientationControls() {
    const btnAuto = document.getElementById('btnAuto');
    const btnPortrait = document.getElementById('btnPortrait');
    const btnLandscape = document.getElementById('btnLandscape');
    
    // Проверяем сохранённую ориентацию
    const savedOrientation = localStorage.getItem('codenames_orientation') || 'auto';
    applyOrientation(savedOrientation);
    
    // Автоповорот
    btnAuto.addEventListener('click', () => {
        applyOrientation('auto');
        showNotification('Автоповорот включён', 'info');
        unlockScreenOrientation();
    });
    
    // Портретная
    btnPortrait.addEventListener('click', () => {
        applyOrientation('portrait');
        showNotification('Портретный режим', 'info');
        lockScreenOrientation('portrait');
    });
    
    // Альбомная
    btnLandscape.addEventListener('click', () => {
        applyOrientation('landscape');
        showNotification('Альбомный режим', 'info');
        lockScreenOrientation('landscape');
    });
}

function applyOrientation(mode) {
    document.body.classList.remove('auto-rotate', 'portrait', 'landscape');
    document.body.classList.add(mode);
    
    // Обновляем активные кнопки
    document.querySelectorAll('.orientation-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    const btnId = `btn${mode.charAt(0).toUpperCase() + mode.slice(1)}`;
    const btn = document.getElementById(btnId);
    if (btn) btn.classList.add('active');
    
    // Сохраняем настройку
    localStorage.setItem('codenames_orientation', mode);
    
    // Перерисовываем поле, если игра загружена
    if (gameData) {
        setTimeout(updateCardLayout, 100);
    }
}

function lockScreenOrientation(orientation) {
    if (screen.orientation && screen.orientation.lock) {
        screen.orientation.lock(orientation).catch(err => {
            console.log('Браузер не поддерживает принудительную ориентацию:', err);
        });
    }
}

function unlockScreenOrientation() {
    if (screen.orientation && screen.orientation.unlock) {
        screen.orientation.unlock();
    }
}

function handleOrientationChange() {
    const orientation = localStorage.getItem('codenames_orientation');
    
    if (orientation === 'auto') {
        setTimeout(updateGameLayout, 300);
    }
}

function updateGameLayout() {
    if (!gameData) return;
    
    // Оптимизируем размер шрифта для текущей ориентации
    const isLandscape = window.innerWidth > window.innerHeight;
    const cards = document.querySelectorAll('.card');
    
    cards.forEach(card => {
        if (isLandscape && window.innerHeight < 600) {
            card.style.fontSize = '11px';
            card.style.padding = '4px';
        } else {
            card.style.fontSize = '';
            card.style.padding = '';
        }
    });
}

function updateCardLayout() {
    const cards = document.querySelectorAll('.card');
    const isLandscape = document.body.classList.contains('landscape') || 
                       (document.body.classList.contains('auto-rotate') && window.innerWidth > window.innerHeight);
    
    cards.forEach(card => {
        if (isLandscape) {
            card.style.aspectRatio = '4/3';
        } else {
            card.style.aspectRatio = '3/4';
        }
    });
}

// ==================== ПОЛНОЭКРАННЫЙ РЕЖИМ ====================
function toggleFullscreen() {
    if (!isFullscreen) {
        enterFullscreen();
    } else {
        exitFullscreen();
    }
}

function enterFullscreen() {
    const elem = document.documentElement;
    
    if (elem.requestFullscreen) {
        elem.requestFullscreen();
    } else if (elem.webkitRequestFullscreen) {
        elem.webkitRequestFullscreen();
    } else if (elem.msRequestFullscreen) {
        elem.msRequestFullscreen();
    } else if (elem.mozRequestFullScreen) {
        elem.mozRequestFullScreen();
    }
    
    elements.btnFullscreen.classList.add('active');
    elements.btnFullscreen.innerHTML = '<i class="fas fa-compress"></i>';
    isFullscreen = true;
    showNotification('Полноэкранный режим', 'success');
}

function exitFullscreen() {
    if (document.exitFullscreen) {
        document.exitFullscreen();
    } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
    } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
    } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen();
    }
    
    elements.btnFullscreen.classList.remove('active');
    elements.btnFullscreen.innerHTML = '<i class="fas fa-expand"></i>';
    isFullscreen = false;
}

function handleFullscreenChange() {
    isFullscreen = !!(document.fullscreenElement || 
                     document.webkitFullscreenElement || 
                     document.mozFullScreenElement || 
                     document.msFullscreenElement);
    
    if (!isFullscreen) {
        elements.btnFullscreen.classList.remove('active');
        elements.btnFullscreen.innerHTML = '<i class="fas fa-expand"></i>';
    }
}

// ==================== WEBSOCKET ПОДКЛЮЧЕНИЕ ====================
function connectWebSocket() {
    if (!roomId) return;
    
    const wsUrl = `wss://${RENDER_URL}/ws?room=${roomId}`;
    
    updateStatus('⌛ Подключение к игровому серверу...', 'connecting');
    
    socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
        updateStatus('✅ Подключено к игровому серверу', 'connected');
        reconnectAttempts = 0;
        showNotification('Соединение установлено', 'success');
        
        // Отправляем пинг каждые 30 секунд
        setInterval(() => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({action: 'ping'}));
            }
        }, 30000);
    };
    
    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        } catch (e) {
            console.error('Ошибка парсинга JSON:', e);
        }
    };
    
    socket.onerror = (error) => {
        console.error('WebSocket ошибка:', error);
        updateStatus('⚠️ Ошибка соединения', 'error');
    };
    
    socket.onclose = (event) => {
        updateStatus('❌ Соединение прервано', 'error');
        
        if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            setTimeout(() => {
                updateStatus(`🔄 Переподключение (${reconnectAttempts}/${maxReconnectAttempts})...`, 'connecting');
                connectWebSocket();
            }, 2000 * reconnectAttempts);
        } else {
            updateStatus('Не удалось подключиться. Обновите страницу.', 'error');
            showNotification('Не удалось подключиться к серверу', 'error');
        }
    };
}

// ==================== ОБРАБОТКА СООБЩЕНИЙ ОТ СЕРВЕРА ====================
function handleServerMessage(data) {
    console.log('📨 Получено от сервера:', data);
    
    switch (data.type) {
        case 'init':
            gameData = data;
            renderGameBoard();
            updateGameInfo();
            elements.gameArea.style.display = 'block';
            updateCardLayout();
            showNotification('Игра загружена!', 'success');
            break;
            
        case 'card_opened':
            if (gameData) {
                gameData.revealed[data.index] = true;
                gameData.current_team = data.current_team;
                updateCard(data.index, data.color);
                updateGameInfo();
                
                if (soundEnabled) {
                    playSound('click');
                }
            }
            break;
            
        case 'player_joined':
            elements.playerCount.textContent = data.count;
            updatePlayersList(data.count);
            showNotification(`Новый игрок подключился! Всего: ${data.count}`, 'info');
            break;
            
        case 'game_over':
            showGameOver(data.winner, data.reason);
            break;
            
        case 'pong':
            // Подтверждение активности
            break;
    }
}

// ==================== СОЗДАНИЕ ИГРОВОГО ПОЛЯ С УДЕРЖАНИЕМ 2000ms ====================
function renderGameBoard() {
    if (!gameData || !gameData.words) {
        console.error('Нет данных для отрисовки игрового поля');
        return;
    }
    
    elements.gameBoard.innerHTML = '';
    holdTimers = {};
    
    gameData.words.forEach((word, index) => {
        const card = document.createElement('div');
        card.className = 'card';
        card.textContent = word;
        card.dataset.index = index;
        
        // Если карточка уже открыта
        if (gameData.revealed[index]) {
            card.classList.add('opened');
            card.classList.add(gameData.colors[index]);
        } else {
            // УСТАНОВКА ОБРАБОТЧИКОВ УДЕРЖАНИЯ 2000ms
            setupCardHoldEvents(card, index);
        }
        
        elements.gameBoard.appendChild(card);
    });
}

function setupCardHoldEvents(card, index) {
    let holdTimer = null;
    let isHolding = false;
    
    // Начало удержания
    const startHold = (e) => {
        if (gameData.revealed[index] || !socket || socket.readyState !== WebSocket.OPEN) {
            return;
        }
        
        e.preventDefault();
        clearTimeout(holdTimer);
        
        card.classList.add('holding');
        isHolding = true;
        
        holdTimer = setTimeout(() => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    action: 'click_card',
                    index: index
                }));
                isHolding = false;
            }
        }, HOLD_DURATION);
        
        holdTimers[index] = holdTimer;
    };
    
    // Конец удержания
    const endHold = () => {
        clearTimeout(holdTimers[index]);
        card.classList.remove('holding');
        
        if (isHolding) {
            // Показываем прогресс удержания (опционально)
            showNotification('Удерживайте 2 секунды для выбора', 'info', 1000);
        }
        
        isHolding = false;
    };
    
    // События для мыши
    card.addEventListener('mousedown', startHold);
    card.addEventListener('mouseup', endHold);
    card.addEventListener('mouseleave', endHold);
    
    // События для касаний (мобильные)
    card.addEventListener('touchstart', (e) => {
        startHold(e);
        if (navigator.vibrate) navigator.vibrate(50); // Вибрация
    }, { passive: false });
    
    card.addEventListener('touchend', endHold);
    card.addEventListener('touchcancel', endHold);
    card.addEventListener('touchmove', (e) => {
        // Отменяем удержание если палец ушёл с карточки
        const touch = e.touches[0];
        const rect = card.getBoundingClientRect();
        
        if (touch.clientX < rect.left || touch.clientX > rect.right ||
            touch.clientY < rect.top || touch.clientY > rect.bottom) {
            endHold();
        }
    });
    
    // Отмена контекстного меню
    card.addEventListener('contextmenu', (e) => e.preventDefault());
}

// ==================== ОБНОВЛЕНИЕ КАРТОЧКИ ====================
function updateCard(index, color) {
    const cards = document.querySelectorAll('.card');
    if (cards[index]) {
        const card = cards[index];
        card.classList.add('opened', color);
        
        // Убираем все обработчики удержания
        card.replaceWith(card.cloneNode(true));
        
        // Обновляем счетчик ходов
        currentMove++;
        elements.currentMove.textContent = currentMove;
        
        // Обновляем статистику
        const opened = gameData.revealed.filter(Boolean).length;
        elements.openedCards.textContent = opened;
    }
}

// ==================== ОБНОВЛЕНИЕ ИНФОРМАЦИИ ОБ ИГРЕ ====================
function updateGameInfo() {
    if (!gameData) return;
    
    // Считаем оставшиеся карточки
    let redLeft = 0;
    let blueLeft = 0;
    
    for (let i = 0; i < 25; i++) {
        if (!gameData.revealed[i]) {
            if (gameData.colors[i] === 'red') redLeft++;
            if (gameData.colors[i] === 'blue') blueLeft++;
        }
    }
    
    // Обновляем счетчики
    elements.redCount.textContent = redLeft;
    elements.blueCount.textContent = blueLeft;
    
    // Обновляем текущую команду
    const teamName = gameData.current_team === 'red' ? 'Красные' : 'Синие';
    const teamClass = gameData.current_team === 'red' ? 'red' : 'blue';
    
    elements.currentTurn.innerHTML = `
        <div class="turn-label">Сейчас ходят:</div>
        <div class="turn-team ${teamClass}">${teamName}</div>
    `;
    
    // Обновляем статистику
    const opened = gameData.revealed.filter(Boolean).length;
    elements.openedCards.textContent = opened;
}

// ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
function copyRoomLink() {
    const link = window.location.href;
    
    navigator.clipboard.writeText(link).then(() => {
        showNotification('✅ Ссылка скопирована в буфер!', 'success');
    }).catch(err => {
        console.error('Ошибка копирования:', err);
        
        // Резервный метод для старых браузеров
        const textArea = document.createElement('textarea');
        textArea.value = link;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        
        showNotification('✅ Ссылка скопирована!', 'success');
    });
}

function toggleMenu() {
    elements.menuContent.style.display = 'block';
    elements.menuOverlay.style.display = 'block';
    document.body.style.overflow = 'hidden';
}

function closeMenu() {
    elements.menuContent.style.display = 'none';
    elements.menuOverlay.style.display = 'none';
    document.body.style.overflow = '';
}

function showRules() {
    elements.rulesModal.classList.add('show');
    closeMenu();
}

function toggleSound() {
    soundEnabled = !soundEnabled;
    const btn = document.getElementById('soundToggle');
    btn.innerHTML = soundEnabled ? 
        '<i class="fas fa-volume-up"></i> Звуки: Вкл' : 
        '<i class="fas fa-volume-mute"></i> Звуки: Выкл';
    
    showNotification(soundEnabled ? 'Звуки включены' : 'Звуки выключены', 'info');
}

function playSound(type) {
    if (!soundEnabled) return;
    
    // Простые звуки через Web Audio API
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        if (type === 'click') {
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);
            oscillator.start();
            oscillator.stop(audioContext.currentTime + 0.1);
        }
    } catch (e) {
        console.log('Web Audio API не поддерживается:', e);
    }
}

function updatePlayersList(count) {
    const playersList = elements.playersList;
    playersList.innerHTML = '';
    
    // Добавляем текущего игрока
    const playerItem = document.createElement('div');
    playerItem.className = 'player-item';
    playerItem.innerHTML = `
        <span class="player-name">Вы</span>
        <span class="player-role agent">Агент</span>
    `;
    playersList.appendChild(playerItem);
    
    // Добавляем других игроков (заглушки)
    for (let i = 1; i < count; i++) {
        const otherPlayer = document.createElement('div');
        otherPlayer.className = 'player-item';
        otherPlayer.innerHTML = `
            <span class="player-name">Игрок ${i + 1}</span>
            <span class="player-role">?</span>
        `;
        playersList.appendChild(otherPlayer);
    }
}

function showGameOver(winner, reason) {
    const winnerName = winner === 'red' ? 'КРАСНЫЕ' : 'СИНИЕ';
    const winnerColor = winner === 'red' ? '#f87171' : '#60a5fa';
    
    const modal = document.createElement('div');
    modal.className = 'modal show';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 400px;">
            <div class="modal-header">
                <h3><i class="fas fa-trophy"></i> Игра окончена!</h3>
            </div>
            <div class="modal-body" style="text-align: center;">
                <div style="font-size: 2rem; color: ${winnerColor}; margin: 20px 0;">
                    <i class="fas fa-crown"></i> ПОБЕДИЛИ ${winnerName}
                </div>
                <p style="color: #94a3b8;">${reason}</p>
                <div style="margin: 30px 0;">
                    <button class="btn-primary" id="btnNewGameModal" style="margin-right: 10px;">
                        <i class="fas fa-redo"></i> Новая игра
                    </button>
                    <button class="btn-secondary" id="btnCopyResults">
                        <i class="fas fa-share"></i> Поделиться
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Обработчики для модального окна
    modal.querySelector('#btnNewGameModal').addEventListener('click', () => {
        location.reload();
    });
    
    modal.querySelector('#btnCopyResults').addEventListener('click', () => {
        const results = `🎮 Codenames - Победили ${winnerName}! ${reason}\nКомната: ${roomId}\nСсылка: ${window.location.href}`;
        navigator.clipboard.writeText(results);
        showNotification('Результаты скопированы!', 'success');
    });
    
    // Закрытие по клику на фон
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
}

// ==================== УВЕДОМЛЕНИЯ И СТАТУС ====================
function updateStatus(text, type) {
    elements.connectionStatus.textContent = text;
    elements.connectionStatus.className = `status ${type}`;
}

function showNotification(message, type = 'info', duration = 3000) {
    const notification = elements.notification;
    
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.classList.add('show');
    
    // Автоматическое скрытие
    setTimeout(() => {
        notification.classList.remove('show');
    }, duration);
    
    // Ручное скрытие по клику
    notification.addEventListener('click', () => {
        notification.classList.remove('show');
    });
}

function showError(title, message) {
    elements.gameArea.innerHTML = `
        <div class="error-container">
            <h2>${title}</h2>
            <p>${message}</p>
            <button class="btn-primary" onclick="location.reload()">
                <i class="fas fa-redo"></i> Попробовать снова
            </button>
        </div>
    `;
}

// ==================== ГОРЯЧИЕ КЛАВИШИ ====================
function handleHotkeys(e) {
    // F - полноэкранный режим
    if (e.key === 'f' || e.key === 'F') {
        toggleFullscreen();
        e.preventDefault();
    }
    
    // ESC - выход из полноэкранного режима
    if (e.key === 'Escape' && isFullscreen) {
        exitFullscreen();
    }
    
    // 1,2,3 - ориентация
    if (e.key === '1') {
        applyOrientation('portrait');
        showNotification('Портретный режим', 'info');
    }
    if (e.key === '2') {
        applyOrientation('landscape');
        showNotification('Альбомный режим', 'info');
    }
    if (e.key === '3') {
        applyOrientation('auto');
        showNotification('Автоповорот', 'info');
    }
    
    // M - меню
    if (e.key === 'm' || e.key === 'M') {
        toggleMenu();
    }
    
    // R - правила
    if (e.key === 'r' || e.key === 'R') {
        showRules();
    }
}

// ==================== ОПТИМИЗАЦИЯ ДЛЯ МОБИЛЬНЫХ ====================
function optimizeForMobile() {
    // Убираем зум при двойном тапе
    document.addEventListener('touchstart', function(event) {
        if (event.touches.length > 1) {
            event.preventDefault();
        }
    }, { passive: false });
    
    let lastTouchEnd = 0;
    document.addEventListener('touchend', function(event) {
        const now = Date.now();
        if (now - lastTouchEnd <= 300) {
            event.preventDefault();
        }
        lastTouchEnd = now;
    }, false);
    
    // Предотвращаем контекстное меню
    document.addEventListener('contextmenu', function(event) {
        if (event.target.classList.contains('card')) {
            event.preventDefault();
        }
    });
    
    // Вибрация при взаимодействии
    if (navigator.vibrate) {
        document.addEventListener('touchstart', function(event) {
            if (event.target.classList.contains('card') && !event.target.classList.contains('opened')) {
                navigator.vibrate(10);
            }
        });
    }
    
    // Определение типа устройства
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    if (isMobile) {
        document.body.classList.add('mobile-device');
        
        // Автоматически предлагаем полноэкранный режим на мобильных
        setTimeout(() => {
            if (!localStorage.getItem('fullscreen_suggested')) {
                showNotification('Нажмите 🖥️ для полноэкранного режима', 'info', 5000);
                localStorage.setItem('fullscreen_suggested', 'true');
            }
        }, 3000);
    }
}

// ==================== АВТОПОДКЛЮЧЕНИЕ ПРИ ВОЗВРАЩЕНИИ НА ВКЛАДКУ ====================
window.addEventListener('focus', () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        if (reconnectAttempts < maxReconnectAttempts) {
            updateStatus('🔄 Восстановление соединения...', 'connecting');
            setTimeout(connectWebSocket, 1000);
        }
    }
});

// ==================== СОХРАНЕНИЕ СОСТОЯНИЯ ПРИ ЗАКРЫТИИ ====================
window.addEventListener('beforeunload', (e) => {
    if (gameData && gameData.revealed.some(r => r)) {
        e.preventDefault();
        e.returnValue = 'У вас есть незавершённая игра. Вы уверены, что хотите уйти?';
    }
});

// ==================== ДЕБАГ ИНФОРМАЦИЯ ====================
console.log(`
╔═══════════════════════════════════════╗
║        CODENAMES ONLINE v${VERSION}        ║
║   Оптимизировано для мобильных устройств  ║
╚═══════════════════════════════════════╝
Доступные функции:
• Удержание карточек: ${HOLD_DURATION}ms
• Полноэкранный режим: F или кнопка 🖥️
• Ориентация: 1-Портретная, 2-Альбомная, 3-Авто
• Меню: M или бургер-кнопка
• Правила: R
• Звуки: ${soundEnabled ? 'Включены' : 'Выключены'}
`);