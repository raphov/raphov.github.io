// ==================== ИГРОВАЯ ЛОГИКА ====================

class GameManager {
    constructor() {
        this.gameState = null;
        this.holdTimers = {};
        this.currentMove = 1;
    }

    /**
     * Отрисовка игрового поля
     */
    renderBoard(gameState) {
        if (!gameState || !gameState.words) {
            console.error('❌ Нет данных для отрисовки');
            return;
        }

        this.gameState = gameState;
        const board = document.getElementById('gameBoard');
        if (!board) return;

        board.innerHTML = '';
        this._clearHoldTimers();

        const isCaptain = gameState.user_role === ROLES.CAPTAIN;
        const userTeam = gameState.user_team;

        gameState.words.forEach((word, index) => {
            const card = this._createCard(word, index, isCaptain, userTeam, gameState);
            board.appendChild(card);
        });

        console.log(`🎮 Поле отрисовано, ${gameState.words.length} карточек`);
    }

    /**
     * Создание карточки
     */
    _createCard(word, index, isCaptain, userTeam, gameState) {
        const card = document.createElement('div');
        card.className = 'card';
        card.textContent = word;
        card.dataset.index = index;
        card.dataset.word = word;

        // Если карточка уже открыта
        if (gameState.revealed[index]) {
            card.classList.add('opened');
            card.classList.add(gameState.colors?.[index] || 'neutral');
        }
        // Если капитан и карточка не открыта - показываем цвет
        else if (isCaptain && gameState.colors) {
            card.classList.add('captain-view');
            card.classList.add(gameState.colors[index]);
            card.style.opacity = '0.85'; // Полупрозрачная для неоткрытых
            card.style.boxShadow = '0 0 15px rgba(255,255,255,0.1)';
            
            // Добавляем подсказку для капитана
            const hint = document.createElement('span');
            hint.className = 'captain-hint';
            hint.textContent = '👑';
            hint.style.cssText = `
                position: absolute;
                top: 5px;
                right: 5px;
                font-size: 14px;
                opacity: 0.7;
            `;
            card.appendChild(hint);
        }
        // Если агент и карточка не открыта
        else {
            card.classList.add('neutral-closed');
            this._setupHoldEvents(card, index);
        }

        return card;
    }

    /**
     * Настройка событий удержания
     */
    _setupHoldEvents(card, index) {
        let holdTimer = null;
        let isHolding = false;
        let holdProgress = 0;
        let progressInterval = null;

        // Индикатор прогресса
        const progressBar = document.createElement('div');
        progressBar.className = 'hold-progress';
        progressBar.style.cssText = `
            position: absolute;
            bottom: 0;
            left: 0;
            width: 0%;
            height: 4px;
            background: linear-gradient(90deg, #fbbf24, #f59e0b);
            border-radius: 0 0 8px 8px;
            transition: width 0.1s linear;
            z-index: 10;
        `;
        card.appendChild(progressBar);

        const startHold = (e) => {
            if (this.gameState?.revealed[index] || !wsManager.isConnected) {
                return;
            }
            
            e.preventDefault();
            this._clearHoldTimer(index);
            
            card.classList.add('holding');
            isHolding = true;
            holdProgress = 0;
            progressBar.style.width = '0%';
            
            // Запускаем прогресс-бар
            progressInterval = setInterval(() => {
                holdProgress += 100 / (CONFIG.HOLD_DURATION / 100);
                progressBar.style.width = Math.min(holdProgress, 100) + '%';
            }, 100);
            
            holdTimer = setTimeout(() => {
                if (wsManager.isConnected) {
                    wsManager.send({
                        action: 'click_card',
                        index: index
                    });
                    
                    // Вибрация на мобильных
                    if (navigator.vibrate) {
                        navigator.vibrate(50);
                    }
                }
                this._clearHoldTimer(index);
            }, CONFIG.HOLD_DURATION);
            
            this.holdTimers[index] = holdTimer;
        };

        const endHold = () => {
            this._clearHoldTimer(index);
            clearInterval(progressInterval);
            card.classList.remove('holding');
            progressBar.style.width = '0%';
            
            if (isHolding) {
                UI.showNotification('Удерживайте 1.5 секунды для выбора', 'info', 1000);
            }
            
            isHolding = false;
        };

        const cancelHold = () => {
            this._clearHoldTimer(index);
            clearInterval(progressInterval);
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
        card.addEventListener('contextmenu', (e) => e.preventDefault());
    }

    /**
     * Обновление карточки после открытия
     */
    updateCard(index, color) {
        const cards = document.querySelectorAll('.card');
        if (!cards[index]) return;
        
        const card = cards[index];
        card.classList.add('opened', color);
        card.style.opacity = '1';
        
        // Убираем прогресс-бар
        const progressBar = card.querySelector('.hold-progress');
        if (progressBar) progressBar.remove();
        
        // Убираем значок капитана
        const captainHint = card.querySelector('.captain-hint');
        if (captainHint) captainHint.remove();
        
        // Убираем все обработчики
        card.replaceWith(card.cloneNode(true));
        
        // Обновляем статистику
        this.currentMove++;
        this._updateStats();
    }

    /**
     * Обновление информации об игре
     */
    updateGameInfo(gameState) {
        this.gameState = gameState;
        
        // Обновляем счёт
        const redCount = document.getElementById('redCount');
        const blueCount = document.getElementById('blueCount');
        const currentTurn = document.getElementById('currentTurn');
        
        if (redCount) redCount.textContent = gameState.red_score || 0;
        if (blueCount) blueCount.textContent = gameState.blue_score || 0;
        
        // Обновляем текущий ход
        if (currentTurn && gameState.current_team) {
            const teamName = TEAM_NAMES[gameState.current_team] || 'Красные';
            const teamClass = gameState.current_team;
            
            currentTurn.innerHTML = `
                <div class="turn-label">Сейчас ходят:</div>
                <div class="turn-team ${teamClass}">${teamName}</div>
            `;
        }
        
        // Обновляем статистику
        this._updateStats();
    }

    /**
     * Обновление статистики
     */
    _updateStats() {
        const openedCards = document.getElementById('openedCards');
        const currentMoveEl = document.getElementById('currentMove');
        
        if (openedCards && this.gameState?.revealed) {
            const opened = this.gameState.revealed.filter(Boolean).length;
            openedCards.textContent = opened;
        }
        
        if (currentMoveEl) {
            currentMoveEl.textContent = this.currentMove;
        }
    }

    /**
     * Очистка таймера удержания
     */
    _clearHoldTimer(index) {
        if (this.holdTimers[index]) {
            clearTimeout(this.holdTimers[index]);
            delete this.holdTimers[index];
        }
    }

    /**
     * Очистка всех таймеров
     */
    _clearHoldTimers() {
        Object.keys(this.holdTimers).forEach(key => {
            clearTimeout(this.holdTimers[key]);
        });
        this.holdTimers = {};
    }

    /**
     * Показ окна победы
     */
    showGameOver(winner, reason) {
        const winnerName = TEAM_NAMES[winner] || winner;
        const winnerColor = getTeamColor(winner);
        
        UI.showModal(
            '🏆 Игра окончена!',
            `
                <div style="text-align: center;">
                    <div style="font-size: 2rem; color: ${winnerColor}; margin: 20px 0;">
                        <i class="fas fa-crown"></i> Победили ${winnerName}
                    </div>
                    <p style="color: #94a3b8;">${reason || 'Поздравляем!'}</p>
                </div>
            `,
            [
                {
                    text: '🔄 Новая игра',
                    class: 'btn-primary',
                    onClick: () => location.reload()
                },
                {
                    text: '📋 Поделиться',
                    class: 'btn-secondary',
                    onClick: async () => {
                        const results = `🎮 Codenames - Победили ${winnerName}!\nКомната: ${this.gameState?.room_id}\nСсылка: ${window.location.href}`;
                        await copyToClipboard(results);
                        UI.showNotification('✅ Результаты скопированы!', 'success');
                    }
                }
            ]
        );
    }
}

// Глобальный экземпляр
const gameManager = new GameManager();

// ==================== ЭКСПОРТ ====================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { GameManager, gameManager };
}