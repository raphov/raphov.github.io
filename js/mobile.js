// ==================== МОБИЛЬНЫЙ МЕНЕДЖЕР (только адаптация) ====================

var MobileManager = {
    isMobile: false,

    init: function() {
        this.isMobile = this._detectMobile();
        if (this.isMobile) {
            document.body.classList.add('mobile-device');
            this._setupMobileOptimizations();
            this._suggestFullscreen();
        }
        // Слушаем повороты и ресайз для подгонки карточек
        this._setupOrientationListeners();
    },

    _detectMobile: function() {
        var ua = navigator.userAgent;
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);
    },

    _setupMobileOptimizations: function() {
        document.addEventListener('touchstart', function(e) {
            if (e.touches.length > 1) e.preventDefault();
        }, { passive: false });
        
        var lastTouchEnd = 0;
        document.addEventListener('touchend', function(e) {
            var now = Date.now();
            if (now - lastTouchEnd <= 300) e.preventDefault();
            lastTouchEnd = now;
        }, false);
        
        document.addEventListener('contextmenu', function(e) {
            if (e.target.classList.contains('card')) e.preventDefault();
        });
    },

    _suggestFullscreen: function() {
        if (!localStorage.getItem('fullscreen_suggested')) {
            setTimeout(function() {
                showNotification('Нажмите 🖥️ для полноэкранного режима', 'info', 5000);
                localStorage.setItem('fullscreen_suggested', 'true');
            }, 3000);
        }
    },

    _adaptCardsToOrientation: function() {
        var isLandscape = window.innerWidth > window.innerHeight;
        var cards = document.querySelectorAll('.card');
        for (var i = 0; i < cards.length; i++) {
            var card = cards[i];
            if (isLandscape) {
                card.style.aspectRatio = '1/1';
                card.style.fontSize = window.innerHeight < 600 ? '11px' : '14px';
                card.style.padding = '4px';
            } else {
                card.style.aspectRatio = '1/1';
                card.style.fontSize = '14px';
                card.style.padding = '6px';
            }
        }
    },

    _setupOrientationListeners: function() {
        var self = this;
        window.addEventListener('orientationchange', function() {
            setTimeout(function() { self._adaptCardsToOrientation(); }, 100);
        });
        window.addEventListener('resize', debounce(function() {
            self._adaptCardsToOrientation();
        }, 100));
    }
};

var mobileManager = MobileManager;