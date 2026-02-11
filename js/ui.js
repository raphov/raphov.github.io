// ==================== UI МЕНЕДЖЕР ====================

var UIManager = {
    elements: {},
    notificationTimeout: null,
    activeModal: null,

    /**
     * Инициализация DOM элементов
     */
    init: function() {
        this.elements = {
            roomDisplay: document.getElementById('roomDisplay'),
            connectionStatus: document.getElementById('connectionStatus'),
            gameArea: document.getElementById('gameArea'),
            gameBoard: document.getElementById('gameBoard'),
            notification: document.getElementById('notification'),
            playerCount: document.getElementById('playerCount'),
            playersList: document.getElementById('playersList'),
            rulesModal: document.getElementById('rulesModal'),
            hotkeysModal: document.getElementById('hotkeysModal'),
            aboutModal: document.getElementById('aboutModal'),
            menuContent: document.getElementById('menuContent'),
            menuOverlay: document.getElementById('menuOverlay'),
            burgerBtn: document.getElementById('burgerBtn'),
            closeMenu: document.getElementById('closeMenu'),
            btnFullscreen: document.getElementById('btnFullscreen'),
            redCount: document.getElementById('redCount'),
            blueCount: document.getElementById('blueCount'),
            currentTurn: document.getElementById('currentTurn'),
            openedCards: document.getElementById('openedCards'),
            currentMove: document.getElementById('currentMove')
        };
        
        return this.elements;
    },

    /**
     * Обновление статуса подключения
     */
    updateConnectionStatus: function(text, type) {
        var status = this.elements.connectionStatus;
        if (!status) return;
        
        status.textContent = text;
        status.className = 'status ' + (type || 'info');
    },

    /**
     * Показ уведомления
     */
    showNotification: function(message, type, duration) {
        var self = this;
        var notification = this.elements.notification;
        if (!notification) return;
        
        if (this.notificationTimeout) {
            clearTimeout(this.notificationTimeout);
        }
        
        notification.textContent = message;
        notification.className = 'notification ' + (type || 'info') + ' show';
        
        this.notificationTimeout = setTimeout(function() {
            notification.classList.remove('show');
        }, duration || 3000);
        
        notification.onclick = function() {
            notification.classList.remove('show');
            clearTimeout(self.notificationTimeout);
        };
    },

    /**
     * Обновление списка игроков
     */
    updatePlayersList: function(count) {
        var list = this.elements.playersList;
        var countEl = this.elements.playerCount;
        
        if (countEl) {
            countEl.textContent = count || 1;
        }
        
        if (!list) return;
        
        list.innerHTML = '';
        
        // Добавляем текущего игрока
        var currentPlayer = document.createElement('div');
        currentPlayer.className = 'player-item';
        currentPlayer.innerHTML = '<span class="player-name">Вы</span>' +
            '<span class="player-role agent">' + (role === 'captain' ? 'Капитан' : 'Агент') + '</span>';
        list.appendChild(currentPlayer);
        
        // Добавляем других игроков (заглушка)
        for (var i = 1; i < (count || 1); i++) {
            var playerEl = document.createElement('div');
            playerEl.className = 'player-item';
            playerEl.innerHTML = '<span class="player-name">Игрок ' + (i + 1) + '</span>' +
                '<span class="player-role">?</span>';
            list.appendChild(playerEl);
        }
    },

    /**
     * Управление меню
     */
    toggleMenu: function() {
        var menu = this.elements.menuContent;
        var overlay = this.elements.menuOverlay;
        
        if (!menu || !overlay) return;
        
        if (menu.style.display === 'block') {
            this.closeMenu();
        } else {
            menu.style.display = 'block';
            overlay.style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
    },

    closeMenu: function() {
        var menu = this.elements.menuContent;
        var overlay = this.elements.menuOverlay;
        
        if (menu) menu.style.display = 'none';
        if (overlay) overlay.style.display = 'none';
        document.body.style.overflow = '';
    },

    /**
     * Полноэкранный режим
     */
    toggleFullscreen: function() {
        if (!document.fullscreenElement) {
            this._enterFullscreen();
        } else {
            this._exitFullscreen();
        }
    },

    _enterFullscreen: function() {
        var elem = document.documentElement;
        
        if (elem.requestFullscreen) {
            elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        } else if (elem.mozRequestFullScreen) {
            elem.mozRequestFullScreen();
        } else if (elem.msRequestFullscreen) {
            elem.msRequestFullscreen();
        } else {
            this.showNotification('Полный экран не поддерживается', 'error');
            return;
        }
        
        if (this.elements.btnFullscreen) {
            this.elements.btnFullscreen.classList.add('active');
            this.elements.btnFullscreen.innerHTML = '<i class="fas fa-compress"></i>';
        }
    },

    _exitFullscreen: function() {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) {
            document.mozCancelFullScreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
        
        if (this.elements.btnFullscreen) {
            this.elements.btnFullscreen.classList.remove('active');
            this.elements.btnFullscreen.innerHTML = '<i class="fas fa-expand"></i>';
        }
    },

    /**
     * Показ ошибки
     */
    showError: function(title, message) {
        var gameArea = this.elements.gameArea;
        if (!gameArea) return;
        
        gameArea.style.display = 'block';
        gameArea.innerHTML = '<div class="error-container">' +
            '<h2>' + title + '</h2>' +
            '<div style="margin: 20px 0;">' + message + '</div>' +
            '<button class="btn-primary" onclick="location.reload()">' +
            '<i class="fas fa-redo"></i> Попробовать снова' +
            '</button>' +
            '</div>';
    },

    /**
     * Показ модального окна правил
     */
    showRules: function() {
        var modal = this.elements.rulesModal;
        if (modal) {
            modal.classList.add('show');
            this.closeMenu();
        }
    },

    /**
     * Показ модального окна горячих клавиш
     */
    showHotkeys: function() {
        var modal = this.elements.hotkeysModal;
        if (modal) {
            modal.classList.add('show');
            this.closeMenu();
        }
    },

    /**
     * Показ информации о проекте
     */
    showAbout: function() {
        var modal = this.elements.aboutModal;
        if (modal) {
            modal.classList.add('show');
            this.closeMenu();
        }
    }
};

// Глобальный экземпляр
var UI = UIManager;
UI.init();