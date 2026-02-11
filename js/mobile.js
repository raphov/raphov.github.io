// ==================== МОБИЛЬНЫЙ МЕНЕДЖЕР ====================

var MobileManager = {
    orientation: 'auto',
    isMobile: false,

    /**
     * Инициализация
     */
    init: function() {
        this.orientation = localStorage.getItem('codenames_orientation') || 'auto';
        this.isMobile = this._detectMobile();
        
        if (this.isMobile) {
            document.body.classList.add('mobile-device');
            this._setupMobileOptimizations();
            this._suggestFullscreen();
        }
        
        this._setupOrientationControls();
        this._setupOrientationListeners();
    },

    /**
     * Определение мобильного устройства
     */
    _detectMobile: function() {
        var ua = navigator.userAgent;
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);
    },

    /**
     * Мобильные оптимизации
     */
    _setupMobileOptimizations: function() {
        // Предотвращаем зум при двойном тапе
        document.addEventListener('touchstart', function(event) {
            if (event.touches.length > 1) {
                event.preventDefault();
            }
        }, { passive: false });
        
        // Предотвращаем масштабирование
        var lastTouchEnd = 0;
        document.addEventListener('touchend', function(event) {
            var now = Date.now();
            if (now - lastTouchEnd <= 300) {
                event.preventDefault();
            }
            lastTouchEnd = now;
        }, false);
        
        // Предотвращаем контекстное меню на карточках
        document.addEventListener('contextmenu', function(event) {
            if (event.target.classList.contains('card')) {
                event.preventDefault();
            }
        });
    },

    /**
     * Предложение полноэкранного режима
     */
    _suggestFullscreen: function() {
        if (!localStorage.getItem('fullscreen_suggested')) {
            setTimeout(function() {
                showNotification('Нажмите 🖥️ для полноэкранного режима', 'info', 5000);
                localStorage.setItem('fullscreen_suggested', 'true');
            }, 3000);
        }
    },

    /**
     * Настройка кнопок ориентации
     */
    _setupOrientationControls: function() {
        var self = this;
        var btnAuto = document.getElementById('btnAuto');
        var btnPortrait = document.getElementById('btnPortrait');
        var btnLandscape = document.getElementById('btnLandscape');
        
        if (!btnAuto || !btnPortrait || !btnLandscape) return;
        
        this._applyOrientation(this.orientation);
        
        btnAuto.addEventListener('click', function() {
            self._setOrientation('auto');
        });
        
        btnPortrait.addEventListener('click', function() {
            self._setOrientation('portrait');
        });
        
        btnLandscape.addEventListener('click', function() {
            self._setOrientation('landscape');
        });
    },

    /**
     * Установка ориентации
     */
    _setOrientation: function(mode) {
        this.orientation = mode;
        this._applyOrientation(mode);
        localStorage.setItem('codenames_orientation', mode);
        
        var modeNames = {
            auto: 'Автоповорот',
            portrait: 'Портретный режим',
            landscape: 'Альбомный режим'
        };
        
        showNotification(modeNames[mode] || mode, 'info');
        
        if (mode === 'portrait') {
            this._lockOrientation('portrait-primary');
        } else if (mode === 'landscape') {
            this._lockOrientation('landscape-primary');
        } else {
            this._unlockOrientation();
        }
    },

    /**
     * Применение ориентации
     */
    _applyOrientation: function(mode) {
        document.body.classList.remove('auto-rotate', 'portrait', 'landscape');
        document.body.classList.add(mode);
        
        // Обновляем активные кнопки
        var buttons = document.querySelectorAll('.orientation-btn');
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].classList.remove('active');
        }
        
        var btnId = 'btn' + mode.charAt(0).toUpperCase() + mode.slice(1);
        var btn = document.getElementById(btnId);
        if (btn) btn.classList.add('active');
        
        // Адаптируем карточки
        this._adaptCardsToOrientation();
    },

    /**
     * Адаптация карточек к ориентации
     */
    _adaptCardsToOrientation: function() {
        var isLandscape = document.body.classList.contains('landscape') || 
                          (document.body.classList.contains('auto-rotate') && window.innerWidth > window.innerHeight);
        
        var cards = document.querySelectorAll('.card');
        for (var i = 0; i < cards.length; i++) {
            var card = cards[i];
            if (isLandscape) {
                card.style.aspectRatio = '4/3';
                if (window.innerHeight < 600) {
                    card.style.fontSize = '11px';
                    card.style.padding = '4px';
                } else {
                    card.style.fontSize = '';
                    card.style.padding = '';
                }
            } else {
                card.style.aspectRatio = '3/4';
                card.style.fontSize = '';
                card.style.padding = '';
            }
        }
    },

    /**
     * Блокировка ориентации экрана
     */
    _lockOrientation: function(orientation) {
        if (screen.orientation && screen.orientation.lock) {
            screen.orientation.lock(orientation).catch(function() {
                showNotification('Поверните телефон вручную', 'info');
            });
        } else if (screen.lockOrientation) {
            screen.lockOrientation(orientation);
        } else {
            showNotification('Поверните телефон вручную', 'info');
        }
    },

    /**
     * Разблокировка ориентации
     */
    _unlockOrientation: function() {
        if (screen.orientation && screen.orientation.unlock) {
            screen.orientation.unlock();
        } else if (screen.unlockOrientation) {
            screen.unlockOrientation();
        }
    },

    /**
     * Настройка слушателей ориентации
     */
    _setupOrientationListeners: function() {
        var self = this;
        
        window.addEventListener('orientationchange', function() {
            setTimeout(function() {
                self._adaptCardsToOrientation();
            }, 300);
        });
        
        window.addEventListener('resize', debounce(function() {
            if (self.orientation === 'auto') {
                self._adaptCardsToOrientation();
            }
        }, 100));
    }
};

// Глобальный экземпляр
var mobileManager = MobileManager;