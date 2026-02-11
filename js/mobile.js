// ==================== МОБИЛЬНЫЙ МЕНЕДЖЕР ====================

class MobileManager {
    constructor() {
        this.orientation = localStorage.getItem('codenames_orientation') || 'auto';
        this.isMobile = this._detectMobile();
    }

    /**
     * Определение мобильного устройства
     */
    _detectMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }

    /**
     * Инициализация
     */
    init() {
        if (this.isMobile) {
            document.body.classList.add('mobile-device');
            this._setupMobileOptimizations();
            this._suggestFullscreen();
        }
        
        this._setupOrientationControls();
        this._setupOrientationListeners();
    }

    /**
     * Мобильные оптимизации
     */
    _setupMobileOptimizations() {
        // Предотвращаем зум при двойном тапе
        document.addEventListener('touchstart', (event) => {
            if (event.touches.length > 1) {
                event.preventDefault();
            }
        }, { passive: false });
        
        // Предотвращаем масштабирование
        let lastTouchEnd = 0;
        document.addEventListener('touchend', (event) => {
            const now = Date.now();
            if (now - lastTouchEnd <= 300) {
                event.preventDefault();
            }
            lastTouchEnd = now;
        }, false);
        
        // Предотвращаем контекстное меню на карточках
        document.addEventListener('contextmenu', (event) => {
            if (event.target.classList.contains('card')) {
                event.preventDefault();
            }
        });
    }

    /**
     * Предложение полноэкранного режима
     */
    _suggestFullscreen() {
        if (!localStorage.getItem('fullscreen_suggested')) {
            setTimeout(() => {
                UI.showNotification('Нажмите 🖥️ для полноэкранного режима', 'info', 5000);
                localStorage.setItem('fullscreen_suggested', 'true');
            }, 3000);
        }
    }

    /**
     * Настройка кнопок ориентации
     */
    _setupOrientationControls() {
        const btnAuto = document.getElementById('btnAuto');
        const btnPortrait = document.getElementById('btnPortrait');
        const btnLandscape = document.getElementById('btnLandscape');
        
        if (!btnAuto || !btnPortrait || !btnLandscape) return;
        
        this._applyOrientation(this.orientation);
        
        btnAuto.addEventListener('click', () => this._setOrientation('auto'));
        btnPortrait.addEventListener('click', () => this._setOrientation('portrait'));
        btnLandscape.addEventListener('click', () => this._setOrientation('landscape'));
    }

    /**
     * Установка ориентации
     */
    _setOrientation(mode) {
        this.orientation = mode;
        this._applyOrientation(mode);
        localStorage.setItem('codenames_orientation', mode);
        
        const modeNames = {
            auto: 'Автоповорот',
            portrait: 'Портретный режим',
            landscape: 'Альбомный режим'
        };
        
        UI.showNotification(modeNames[mode] || mode, 'info');
        
        if (mode === 'portrait') {
            this._lockOrientation('portrait-primary');
        } else if (mode === 'landscape') {
            this._lockOrientation('landscape-primary');
        } else {
            this._unlockOrientation();
        }
    }

    /**
     * Применение ориентации
     */
    _applyOrientation(mode) {
        document.body.classList.remove('auto-rotate', 'portrait', 'landscape');
        document.body.classList.add(mode);
        
        // Обновляем активные кнопки
        document.querySelectorAll('.orientation-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const btnId = `btn${mode.charAt(0).toUpperCase() + mode.slice(1)}`;
        const btn = document.getElementById(btnId);
        if (btn) btn.classList.add('active');
        
        // Адаптируем карточки
        this._adaptCardsToOrientation();
    }

    /**
     * Адаптация карточек к ориентации
     */
    _adaptCardsToOrientation() {
        const isLandscape = document.body.classList.contains('landscape') || 
                           (document.body.classList.contains('auto-rotate') && window.innerWidth > window.innerHeight);
        
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => {
            if (isLandscape) {
                card.style.aspectRatio = '4/3';
            } else {
                card.style.aspectRatio = '3/4';
            }
            
            // Адаптация размера шрифта
            if (isLandscape && window.innerHeight < 600) {
                card.style.fontSize = '11px';
                card.style.padding = '4px';
            } else {
                card.style.fontSize = '';
                card.style.padding = '';
            }
        });
    }

    /**
     * Блокировка ориентации экрана
     */
    _lockOrientation(orientation) {
        if (screen.orientation && screen.orientation.lock) {
            screen.orientation.lock(orientation).catch(() => {
                UI.showNotification('Поверните телефон вручную', 'info');
            });
        } else if (screen.lockOrientation) {
            screen.lockOrientation(orientation);
        } else {
            UI.showNotification('Поверните телефон вручную', 'info');
        }
    }

    /**
     * Разблокировка ориентации
     */
    _unlockOrientation() {
        if (screen.orientation && screen.orientation.unlock) {
            screen.orientation.unlock();
        } else if (screen.unlockOrientation) {
            screen.unlockOrientation();
        }
    }

    /**
     * Настройка слушателей ориентации
     */
    _setupOrientationListeners() {
        window.addEventListener('orientationchange', () => {
            setTimeout(() => this._adaptCardsToOrientation(), 300);
        });
        
        window.addEventListener('resize', debounce(() => {
            if (this.orientation === 'auto') {
                this._adaptCardsToOrientation();
            }
        }, 100));
    }
}

// Глобальный экземпляр
const mobileManager = new MobileManager();

// ==================== ЭКСПОРТ ====================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { MobileManager, mobileManager };
}