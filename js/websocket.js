// ==================== WEBSOCKET МЕНЕДЖЕР ====================

class WebSocketManager {
    constructor() {
        this.socket = null;
        this.roomId = null;
        this.userId = null;
        this.reconnectAttempts = 0;
        this.maxAttempts = CONFIG.MAX_RECONNECT_ATTEMPTS;
        this.messageHandlers = new Map();
        this.pingInterval = null;
        this.isConnected = false;
    }

    /**
     * Подключение к WebSocket
     */
    connect(roomId, userId) {
        if (!roomId || !userId) {
            console.error('❌ Нет roomId или userId');
            return false;
        }

        this.roomId = roomId;
        this.userId = userId;

        const wsUrl = `wss://${CONFIG.RENDER_URL}/ws?room=${roomId}&user_id=${userId}`;
        
        this.socket = new WebSocket(wsUrl);
        this._setupEventListeners();
        
        return true;
    }

    /**
     * Настройка обработчиков событий
     */
    _setupEventListeners() {
        this.socket.onopen = () => this._handleOpen();
        this.socket.onmessage = (event) => this._handleMessage(event);
        this.socket.onerror = (error) => this._handleError(error);
        this.socket.onclose = (event) => this._handleClose(event);
    }

    /**
     * Обработчик открытия соединения
     */
    _handleOpen() {
        console.log('✅ WebSocket подключен');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        
        // Запускаем пинг
        this._startPing();
        
        // Запрашиваем состояние игры
        this.send({ action: 'get_state' });
        
        // Вызываем обработчики
        this._emit('connected');
    }

    /**
     * Обработчик входящих сообщений
     */
    _handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('📨 Получено:', data.type);
            
            // Вызываем обработчики для конкретного типа сообщения
            this._emit(data.type, data);
            
            // Общий обработчик
            this._emit('message', data);
            
        } catch (e) {
            console.error('❌ Ошибка парсинга JSON:', e);
        }
    }

    /**
     * Обработчик ошибок
     */
    _handleError(error) {
        console.error('❌ WebSocket ошибка:', error);
        this._emit('error', error);
    }

    /**
     * Обработчик закрытия соединения
     */
    _handleClose(event) {
        console.log('❌ WebSocket отключен');
        this.isConnected = false;
        this._stopPing();
        this._emit('disconnected', event);
        
        // Пытаемся переподключиться
        this._reconnect();
    }

    /**
     * Переподключение
     */
    _reconnect() {
        if (this.reconnectAttempts >= this.maxAttempts) {
            console.error('❌ Превышено количество попыток переподключения');
            this._emit('reconnect_failed');
            return;
        }

        this.reconnectAttempts++;
        const delay = 2000 * this.reconnectAttempts;
        
        console.log(`🔄 Переподключение через ${delay}ms (${this.reconnectAttempts}/${this.maxAttempts})`);
        this._emit('reconnecting', { attempt: this.reconnectAttempts, delay });
        
        setTimeout(() => {
            if (this.roomId && this.userId) {
                this.connect(this.roomId, this.userId);
            }
        }, delay);
    }

    /**
     * Отправка сообщения
     */
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
            return true;
        }
        return false;
    }

    /**
     * Запуск пинга
     */
    _startPing() {
        this._stopPing();
        this.pingInterval = setInterval(() => {
            if (this.isConnected) {
                this.send({ action: 'ping' });
            }
        }, CONFIG.PING_INTERVAL);
    }

    /**
     * Остановка пинга
     */
    _stopPing() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    /**
     * Подписка на события
     */
    on(event, callback) {
        if (!this.messageHandlers.has(event)) {
            this.messageHandlers.set(event, []);
        }
        this.messageHandlers.get(event).push(callback);
    }

    /**
     * Отписка от событий
     */
    off(event, callback) {
        if (this.messageHandlers.has(event)) {
            const handlers = this.messageHandlers.get(event);
            const index = handlers.indexOf(callback);
            if (index !== -1) {
                handlers.splice(index, 1);
            }
        }
    }

    /**
     * Вызов обработчиков
     */
    _emit(event, data) {
        if (this.messageHandlers.has(event)) {
            this.messageHandlers.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (e) {
                    console.error(`❌ Ошибка в обработчике ${event}:`, e);
                }
            });
        }
    }

    /**
     * Закрытие соединения
     */
    disconnect() {
        this._stopPing();
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.isConnected = false;
    }
}

// Создаём глобальный экземпляр
const wsManager = new WebSocketManager();

// ==================== ЭКСПОРТ ====================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WebSocketManager, wsManager };
}