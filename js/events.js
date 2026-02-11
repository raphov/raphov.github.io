// ==================== МЕНЕДЖЕР СОБЫТИЙ ====================

class EventManager {
    constructor() {
        this.hotkeys = {
            'f': () => UI.toggleFullscreen(),
            'F': () => UI.toggleFullscreen(),
            'Escape': () => this._handleEscape(),
            '1': () => mobileManager._setOrientation('portrait'),
            '2': () => mobileManager._setOrientation('landscape'),
            '3': () => mobileManager._setOrientation('auto'),
            'm': () => UI.toggleMenu(),
            'M': () => UI.toggleMenu(),
            'r': () => this._showRules(),
            'R': () => this._showRules(),
            'c': () => this._copyLink(),
            'C': () => this._copyLink()
        };
    }

    /**
     * Инициализация всех обработчиков
     */
    init() {
        this._setupGlobalEvents();
        this._setupButtonEvents();
        this._setupModalEvents();
        this._setupHotkeys();
    }

    /**
     * Глобальные события
     */
    _setupGlobalEvents() {
        // Подтверждение ухода со страницы
        window.addEventListener('beforeunload', (e) => {
            if (gameManager.gameState?.revealed?.some(Boolean)) {
                e.preventDefault();
                e.returnValue = 'У вас есть незавершённая игра. Вы уверены?';
            }
        });
        
        // Восстановление соединения при возвращении
        window.addEventListener('focus', () => {
            if (!wsManager.isConnected) {
                const params = getUrlParams();
                if (params.roomId && params.userId) {
                    wsManager.connect(params.roomId, params.userId);
                }
            }
        });
        
        // Отслеживание полноэкранного режима
        document.addEventListener('fullscreenchange', () => this._updateFullscreenButton());
        document.addEventListener('webkitfullscreenchange', () => this._updateFullscreenButton());
        document.addEventListener('mozfullscreenchange', () => this._updateFullscreenButton());
    }

    /**
     * Кнопки интерфейса
     */
    _setupButtonEvents() {
        // Копирование ссылки
        const btnCopyLink = document.getElementById('btnCopyLink');
        if (btnCopyLink) {
            btnCopyLink.addEventListener('click', () => this._copyLink());
        }
        
        // Новая игра
        const btnNewGame = document.getElementById('btnNewGame');
        if (btnNewGame) {
            btnNewGame.addEventListener('click', () => {
                if (confirm('Создать новую игру? Текущий прогресс будет потерян.')) {
                    location.reload();
                }
            });
        }
        
        // Бургер-меню
        const burgerBtn = document.getElementById('burgerBtn');
        const closeMenu = document.getElementById('closeMenu');
        const menuOverlay = document.getElementById('menuOverlay');
        
        if (burgerBtn) burgerBtn.addEventListener('click', () => UI.toggleMenu());
        if (closeMenu) closeMenu.addEventListener('click', () => UI.closeMenu());
        if (menuOverlay) menuOverlay.addEventListener('click', () => UI.closeMenu());
        
        // Полноэкранный режим
        const btnFullscreen = document.getElementById('btnFullscreen');
        if (btnFullscreen) {
            btnFullscreen.addEventListener('click', () => UI.toggleFullscreen());
        }
        
        // Кнопки меню
        this._setupMenuButtons();
    }

    /**
     * Кнопки в меню
     */
    _setupMenuButtons() {
        // Правила
        const showRules = document.getElementById('showRules');
        if (showRules) {
            showRules.addEventListener('click', () => this._showRules());
        }
        
        // Горячие клавиши
        const showHotkeys = document.getElementById('showHotkeys');
        if (showHotkeys) {
            showHotkeys.addEventListener('click', () => this._showHotkeys());
        }
        
        // О проекте
        const showAbout = document.getElementById('showAbout');
        if (showAbout) {
            showAbout.addEventListener('click', () => this._showAbout());
        }
        
        // Звук
        const soundToggle = document.getElementById('soundToggle');
        if (soundToggle) {
            soundToggle.addEventListener('click', () => this._toggleSound());
        }
        
        // Смена роли
        const changeRole = document.getElementById('changeRole');
        if (changeRole) {
            changeRole.addEventListener('click', () => {
                UI.showNotification('Роль можно сменить только при создании комнаты', 'info');
            });
        }
    }

    /**
     * Модальные окна
     */
    _setupModalEvents() {
        // Модальное окно правил
        const rulesModal = document.getElementById('rulesModal');
        if (rulesModal) {
            const closeBtn = rulesModal.querySelector('.modal-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => rulesModal.classList.remove('show'));
            }
            
            rulesModal.addEventListener('click', (e) => {
                if (e.target === rulesModal) {
                    rulesModal.classList.remove('show');
                }
            });
        }
        
        // Аналогично для других модалок
        ['hotkeysModal', 'aboutModal'].forEach(modalId => {
            const modal = document.getElementById(modalId);
            if (modal) {
                const closeBtn = modal.querySelector('.modal-close');
                if (closeBtn) {
                    closeBtn.addEventListener('click', () => modal.classList.remove('show'));
                }
                
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        modal.classList.remove('show');
                    }
                });
            }
        });
    }

    /**
     * Горячие клавиши
     */
    _setupHotkeys() {
        document.addEventListener('keydown', (e) => {
            const handler = this.hotkeys[e.key];
            if (handler) {
                e.preventDefault();
                handler();
            }
        });
    }

    /**
     * Обработка Escape
     */
    _handleEscape() {
        // Закрываем меню
        UI.closeMenu();
        
        // Закрываем модальные окна
        document.querySelectorAll('.modal.show').forEach(modal => {
            modal.classList.remove('show');
        });
        
        // Выходим из полноэкранного режима
        if (document.fullscreenElement) {
            UI._exitFullscreen();
        }
    }

    /**
     * Копирование ссылки
     */
    async _copyLink() {
        const success = await copyToClipboard(window.location.href);
        if (success) {
            UI.showNotification('✅ Ссылка скопирована!', 'success');
        } else {
            UI.showNotification('❌ Ошибка копирования', 'error');
        }
    }

    /**
     * Показ правил
     */
    _showRules() {
        const modal = document.getElementById('rulesModal');
        if (modal) {
            modal.classList.add('show');
            UI.closeMenu();
        }
    }

    /**
     * Показ горячих клавиш
     */
    _showHotkeys() {
        const modal = document.getElementById('hotkeysModal');
        if (modal) {
            modal.classList.add('show');
            UI.closeMenu();
        }
    }

    /**
     * Показ информации о проекте
     */
    _showAbout() {
        const modal = document.getElementById('aboutModal');
        if (modal) {
            modal.classList.add('show');
            UI.closeMenu();
        }
    }

    /**
     * Переключение звука
     */
    _toggleSound() {
        const btn = document.getElementById('soundToggle');
        const isEnabled = btn?.innerHTML.includes('Вкл');
        
        if (btn) {
            btn.innerHTML = isEnabled ? 
                '<i class="fas fa-volume-mute"></i> Звуки: Выкл' : 
                '<i class="fas fa-volume-up"></i> Звуки: Вкл';
        }
        
        UI.showNotification(isEnabled ? '🔇 Звуки выключены' : '🔊 Звуки включены', 'info');
    }

    /**
     * Обновление кнопки полноэкранного режима
     */
    _updateFullscreenButton() {
        const btn = document.getElementById('btnFullscreen');
        if (!btn) return;
        
        const isFullscreen = !!document.fullscreenElement;
        
        btn.classList.toggle('active', isFullscreen);
        btn.innerHTML = isFullscreen ? 
            '<i class="fas fa-compress"></i>' : 
            '<i class="fas fa-expand"></i>';
    }
}

// Глобальный экземпляр
const eventManager = new EventManager();

// ==================== ЭКСПОРТ ====================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EventManager, eventManager };
}