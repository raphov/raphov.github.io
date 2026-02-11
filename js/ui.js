// ==================== UI МЕНЕДЖЕР ====================

class UIManager {
    constructor() {
        this.elements = this._getElements();
        this.notificationTimeout = null;
        this.activeModal = null;
    }

    /**
     * Получение DOM элементов
     */
    _getElements() {
        return {
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
            btnFullscreen: document.getElementById('btnFullscreen')
        };
    }

    /**
     * Обновление статуса подключения
     */
    updateConnectionStatus(text, type = 'info') {
        const status = this.elements.connectionStatus;
        if (!status) return;
        
        status.textContent = text;
        status.className = `status ${type}`;
    }

    /**
     * Показ уведомления
     */
    showNotification(message, type = 'info', duration = 3000) {
        const notification = this.elements.notification;
        if (!notification) return;
        
        // Очищаем предыдущий таймер
        if (this.notificationTimeout) {
            clearTimeout(this.notificationTimeout);
        }
        
        notification.textContent = message;
        notification.className = `notification ${type} show`;
        
        // Авто-скрытие
        this.notificationTimeout = setTimeout(() => {
            notification.classList.remove('show');
        }, duration);
        
        // Ручное скрытие по клику
        notification.onclick = () => {
            notification.classList.remove('show');
            clearTimeout(this.notificationTimeout);
        };
    }

    /**
     * Показ модального окна
     */
    showModal(title, content, buttons = []) {
        const modalId = 'dynamic-modal-' + Date.now();
        const modal = document.createElement('div');
        modal.id = modalId;
        modal.className = 'modal show';
        
        let buttonsHtml = '';
        buttons.forEach(btn => {
            buttonsHtml += `<button class="${btn.class}" onclick="(${btn.onClick})()">${btn.text}</button>`;
        });
        
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 500px;">
                <div class="modal-header">
                    <h3>${title}</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    ${content}
                    ${buttons.length ? `<div style="display: flex; gap: 15px; justify-content: center; margin-top: 30px;">${buttonsHtml}</div>` : ''}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        this.activeModal = modal;
        
        // Закрытие по крестику
        modal.querySelector('.modal-close').onclick = () => {
            document.body.removeChild(modal);
            this.activeModal = null;
        };
        
        // Закрытие по клику на фон
        modal.onclick = (e) => {
            if (e.target === modal) {
                document.body.removeChild(modal);
                this.activeModal = null;
            }
        };
    }

    /**
     * Обновление списка игроков
     */
    updatePlayersList(count, players = []) {
        const list = this.elements.playersList;
        const countEl = this.elements.playerCount;
        
        if (countEl) {
            countEl.textContent = count;
        }
        
        if (!list) return;
        
        list.innerHTML = '';
        
        // Добавляем текущего игрока
        const currentPlayer = document.createElement('div');
        currentPlayer.className = 'player-item';
        currentPlayer.innerHTML = `
            <span class="player-name">Вы</span>
            <span class="player-role agent">Агент</span>
        `;
        list.appendChild(currentPlayer);
        
        // Добавляем других игроков
        for (let i = 1; i < count; i++) {
            const player = players[i - 1] || { name: `Игрок ${i + 1}`, role: '?' };
            const playerEl = document.createElement('div');
            playerEl.className = 'player-item';
            playerEl.innerHTML = `
                <span class="player-name">${player.name || `Игрок ${i + 1}`}</span>
                <span class="player-role">${player.role || '?'}</span>
            `;
            list.appendChild(playerEl);
        }
    }

    /**
     * Управление меню
     */
    toggleMenu() {
        const menu = this.elements.menuContent;
        const overlay = this.elements.menuOverlay;
        
        if (!menu || !overlay) return;
        
        if (menu.style.display === 'block') {
            this.closeMenu();
        } else {
            menu.style.display = 'block';
            overlay.style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
    }

    closeMenu() {
        const menu = this.elements.menuContent;
        const overlay = this.elements.menuOverlay;
        
        if (menu) menu.style.display = 'none';
        if (overlay) overlay.style.display = 'none';
        document.body.style.overflow = '';
    }

    /**
     * Полноэкранный режим
     */
    toggleFullscreen() {
        if (!document.fullscreenElement) {
            this._enterFullscreen();
        } else {
            this._exitFullscreen();
        }
    }

    _enterFullscreen() {
        const elem = document.documentElement;
        
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
    }

    _exitFullscreen() {
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
    }

    /**
     * Показ ошибки
     */
    showError(title, message) {
        const gameArea = this.elements.gameArea;
        if (!gameArea) return;
        
        gameArea.style.display = 'block';
        gameArea.innerHTML = `
            <div class="error-container">
                <h2>${title}</h2>
                <div style="margin: 20px 0;">${message}</div>
                <button class="btn-primary" onclick="location.reload()">
                    <i class="fas fa-redo"></i> Попробовать снова
                </button>
            </div>
        `;
    }
}

// Глобальный экземпляр
const UI = new UIManager();

// ==================== ЭКСПОРТ ====================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { UIManager, UI };
}