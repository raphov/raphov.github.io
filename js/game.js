// ==================== ИГРОВАЯ ЛОГИКА ====================

var GameManager = {
    gameState: null,
    holdTimers: {},
    currentMove: 1,

    /**
     * Отрисовка игрового поля
     */
    renderBoard: function(gameState) {
        if (!gameState || !gameState.words) {
            console.error('❌ Нет данных для отрисовки');
            return;
        }

        this.gameState = gameState;
        var board = document.getElementById('gameBoard');
        if (!board) return;

        board.innerHTML = '';
        this._clearHoldTimers();

        var isCaptain = (gameState.role === ROLES.CAPTAIN);
        var words = gameState.words;

        for (var i = 0; i < words.length; i++) {
            var card = this._createCard(words[i], i, isCaptain, gameState);
            board.appendChild(card);
        }

        console.log('🎮 Поле отрисовано, ' + words.length + ' карточек');
    },

     /**
     * Создание карточки
     */
    _createCard: function(word, index, isCaptain, gameState) {
        var card = document.createElement('div');
        card.className = 'card';
        card.textContent = word;
        card.dataset.index = index;
        card.dataset.word = word;

        // Если карточка уже открыта
        if (gameState.revealed[index]) {
            card.classList.add('opened');
            if (gameState.colors && gameState.colors[index]) {
                card.classList.add(gameState.colors[index]);
            }
        }
        // Если капитан и карточка не открыта – показываем цвет
        else if (isCaptain && gameState.colors) {
            card.classList.add('captain-view');
            card.classList.add(gameState.colors[index]);
            card.style.opacity = '0.85';
            // ❌ Короны убраны – больше не добавляем hint с короной
        }
        // Если агент и карточка не открыта
        else {
            card.classList.add('neutral-closed');
            this._setupHoldEvents(card, index);
        }

        return card;
    },


    /**
     * Настройка событий удержания
     */
    _setupHoldEvents: function(card, index) {
        var self = this;
        var holdTimer = null;
        var isHolding = false;
        var holdProgress = 0;
        var progressInterval = null;

        // Индикатор прогресса
        var progressBar = document.createElement('div');
        progressBar.className = 'hold-progress';
        progressBar.style.cssText = 'position: absolute; bottom: 0; left: 0; width: 0%; height: 4px; background: linear-gradient(90deg, #fbbf24, #f59e0b); border-radius: 0 0 8px 8px; transition: width 0.1s linear; z-index: 10;';
        card.appendChild(progressBar);

        var startHold = function(e) {
            if (self.gameState && self.gameState.revealed[index]) {
                return;
            }
            if (!wsManager.isConnected) {
                showNotification('Нет соединения с сервером', 'error');
                return;
            }
            
            e.preventDefault();
            self._clearHoldTimer(index);
            
            card.classList.add('holding');
            isHolding = true;
            holdProgress = 0;
            progressBar.style.width = '0%';
            
            // Запускаем прогресс-бар
            progressInterval = setInterval(function() {
                holdProgress += 100 / (CONFIG.HOLD_DURATION / 100);
                progressBar.style.width = Math.min(holdProgress, 100) + '%';
            }, 100);
            
            holdTimer = setTimeout(function() {
                if (wsManager.isConnected) {
                    wsManager.send({
                        action: 'click_card',
                        index: index
                    });
                    if (navigator.vibrate) {
                        navigator.vibrate(50);
                    }
                }
                isHolding = false; // ⬅️ ВАЖНО: сбрасываем флаг, чтобы не показывать уведомление
                self._clearHoldTimer(index);
            }, CONFIG.HOLD_DURATION);
            
            self.holdTimers[index] = holdTimer;
        };

        var endHold = function() {
            self._clearHoldTimer(index);
            if (progressInterval) {
                clearInterval(progressInterval);
            }
            card.classList.remove('holding');
            progressBar.style.width = '0%';
            
            if (isHolding) {
                showNotification('Удерживайте 2 секунды для выбора', 'info', 1000);
            }
            
            isHolding = false;
        };

        var cancelHold = function() {
            self._clearHoldTimer(index);
            if (progressInterval) {
                clearInterval(progressInterval);
            }
            card.classList.remove('holding');
            progressBar.style.width = '0%';
            isHolding = false;
        };

        // События мыши
        card.addEventListener('mousedown', startHold);
        card.addEventListener('mouseup', endHold);
        card.addEventListener('mouseleave', cancelHold);
        
        // События касания
        card.addEventListener('touchstart', startHold, { passive: false });
        card.addEventListener('touchend', endHold);
        card.addEventListener('touchcancel', cancelHold);
        
        // Отмена контекстного меню
        card.addEventListener('contextmenu', function(e) {
            e.preventDefault();
        });
    },

     /**
     * Обновление карточки после открытия и счётчиков
     */
        updateCard: function(index, color, redScore, blueScore) {
            var cards = document.querySelectorAll('.card');
            if (!cards[index]) return;
            
            var card = cards[index];
            card.classList.add('opened', color);
            card.style.opacity = '1';
            
            var progressBar = card.querySelector('.hold-progress');
            if (progressBar) progressBar.remove();
            
            var newCard = card.cloneNode(true);
            card.parentNode.replaceChild(newCard, card);
            
            // ⬇️ ОБНОВЛЯЕМ СЧЁТЧИКИ
            var redCount = document.getElementById('redCount');
            var blueCount = document.getElementById('blueCount');
            if (redCount && redScore !== undefined) redCount.textContent = redScore;
            if (blueCount && blueScore !== undefined) blueCount.textContent = blueScore;
            
            this.currentMove++;
            this._updateStats();
        },

    /**
     * Обновление информации об игре
     */
    updateGameInfo: function(gameState) {
        this.gameState = gameState;
        
        // Обновляем счёт
        var redCount = document.getElementById('redCount');
        var blueCount = document.getElementById('blueCount');
        var currentTurn = document.getElementById('currentTurn');
        
        if (redCount) redCount.textContent = gameState.red_score || 0;
        if (blueCount) blueCount.textContent = gameState.blue_score || 0;
        
        // Обновляем текущий ход
        if (currentTurn && gameState.current_team) {
            var teamName = TEAM_NAMES[gameState.current_team] || 'Красные';
            var teamClass = gameState.current_team;
            
            currentTurn.innerHTML = '<div class="turn-label">Сейчас ходят:</div>' +
                '<div class="turn-team ' + teamClass + '">' + teamName + '</div>';
        }
        
        // Обновляем статистику
        this._updateStats();
    },

    /**
     * Обновление статистики
     */
    _updateStats: function() {
        var openedCards = document.getElementById('openedCards');
        var currentMoveEl = document.getElementById('currentMove');
        
        if (openedCards && this.gameState && this.gameState.revealed) {
            var opened = 0;
            for (var i = 0; i < this.gameState.revealed.length; i++) {
                if (this.gameState.revealed[i]) opened++;
            }
            openedCards.textContent = opened;
        }
        
        if (currentMoveEl) {
            currentMoveEl.textContent = this.currentMove;
        }
    },

    /**
     * Очистка таймера удержания
     */
    _clearHoldTimer: function(index) {
        if (this.holdTimers[index]) {
            clearTimeout(this.holdTimers[index]);
            delete this.holdTimers[index];
        }
    },

    /**
     * Очистка всех таймеров
     */
    _clearHoldTimers: function() {
        for (var key in this.holdTimers) {
            clearTimeout(this.holdTimers[key]);
        }
        this.holdTimers = {};
    },

    /**
     * Показ окна победы
     */
    showGameOver: function(winner, reason) {
        var winnerName = TEAM_NAMES[winner] || winner;
        var winnerColor = getTeamColor(winner);
        
        var modal = document.createElement('div');
        modal.className = 'modal show';
        modal.innerHTML = '<div class="modal-content" style="max-width: 500px;">' +
            '<div class="modal-header">' +
            '<h3>🏆 Игра окончена!</h3>' +
            '<button class="modal-close">&times;</button>' +
            '</div>' +
            '<div class="modal-body" style="text-align: center;">' +
            '<div style="font-size: 2rem; color: ' + winnerColor + '; margin: 20px 0;">' +
            '<i class="fas fa-crown"></i> Победили ' + winnerName +
            '</div>' +
            '<p style="color: #94a3b8;">' + (reason || 'Поздравляем!') + '</p>' +
            '<div style="display: flex; gap: 15px; justify-content: center; margin-top: 30px;">' +
            '<button class="btn-primary" onclick="location.reload()">🔄 Новая игра</button>' +
            '<button class="btn-secondary" id="shareResultsBtn">📋 Поделиться</button>' +
            '</div>' +
            '</div>' +
            '</div>';
        
        document.body.appendChild(modal);
        
        // Закрытие по крестику
        var closeBtn = modal.querySelector('.modal-close');
        closeBtn.onclick = function() {
            document.body.removeChild(modal);
        };
        
        // Закрытие по клику на фон
        modal.onclick = function(e) {
            if (e.target === modal) {
                document.body.removeChild(modal);
            }
        };
        
        // Кнопка поделиться
        var shareBtn = modal.querySelector('#shareResultsBtn');
        if (shareBtn) {
            shareBtn.onclick = function() {
                var results = '🎮 Codenames - Победили ' + winnerName + '!\nКомната: ' + (gameManager.gameState ? gameManager.gameState.room_id : '') + '\nСсылка: ' + window.location.href;
                copyToClipboard(results);
                showNotification('✅ Результаты скопированы!', 'success');
            };
        }
    }
};

// Глобальный экземпляр
var gameManager = GameManager;