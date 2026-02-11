// ==================== WEBSOCKET МЕНЕДЖЕР ====================

var WebSocketManager = {
    socket: null,
    roomId: null,
    role: null,
    reconnectAttempts: 0,
    maxAttempts: CONFIG.MAX_RECONNECT_ATTEMPTS,
    isConnected: false,
    messageHandlers: {},
    pingInterval: null,

    /**
     * Подключение к WebSocket
     */
    connect: function(roomId, role) {
        if (!roomId || !role) {
            console.error('❌ Нет roomId или role');
            return false;
        }

        this.roomId = roomId;
        this.role = role;

        var wsUrl = 'wss://' + CONFIG.RENDER_URL + '/ws?room=' + roomId + '&role=' + role;
        console.log('🔌 Подключение к WebSocket:', wsUrl);
        
        this.socket = new WebSocket(wsUrl);
        this._setupEventListeners();
        
        return true;
    },

    /**
     * Настройка обработчиков событий
     */
    _setupEventListeners: function() {
        var self = this;
        
        this.socket.onopen = function() {
            self._handleOpen();
        };
        
        this.socket.onmessage = function(event) {
            self._handleMessage(event);
        };
        
        this.socket.onerror = function(error) {
            self._handleError(error);
        };
        
        this.socket.onclose = function(event) {
            self._handleClose(event);
        };
    },

    /**
     * Обработчик открытия соединения
     */
    _handleOpen: function() {
        console.log('✅ WebSocket подключен');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this._startPing();
        this._emit('connected');
    },

    /**
     * Обработчик входящих сообщений
     */
    _handleMessage: function(event) {
        try {
            var data = JSON.parse(event.data);
            console.log('📨 Получено:', data.type);
            this._emit(data.type, data);
            this._emit('message', data);
        } catch (e) {
            console.error('❌ Ошибка парсинга JSON:', e);
        }
    },

    /**
     * Обработчик ошибок
     */
    _handleError: function(error) {
        console.error('❌ WebSocket ошибка:', error);
        this._emit('error', error);
    },

    /**
     * Обработчик закрытия соединения
     */
    _handleClose: function(event) {
        console.log('❌ WebSocket отключен');
        this.isConnected = false;
        this._stopPing();
        this._emit('disconnected', event);
        this._reconnect();
    },

    /**
     * Переподключение
     */
    _reconnect: function() {
        var self = this;
        
        if (this.reconnectAttempts >= this.maxAttempts) {
            console.error('❌ Превышено количество попыток переподключения');
            this._emit('reconnect_failed');
            return;
        }

        this.reconnectAttempts++;
        var delay = 2000 * this.reconnectAttempts;
        
        console.log('🔄 Переподключение через ' + delay + 'ms (' + this.reconnectAttempts + '/' + this.maxAttempts + ')');
        this._emit('reconnecting', { attempt: this.reconnectAttempts, delay: delay });
        
        setTimeout(function() {
            if (self.roomId && self.role) {
                self.connect(self.roomId, self.role);
            }
        }, delay);
    },

    /**
     * Отправка сообщения
     */
    send: function(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
            return true;
        }
        return false;
    },

    /**
     * Запуск пинга
     */
    _startPing: function() {
        var self = this;
        this._stopPing();
        this.pingInterval = setInterval(function() {
            if (self.isConnected) {
                self.send({ action: 'ping' });
            }
        }, CONFIG.PING_INTERVAL);
    },

    /**
     * Остановка пинга
     */
    _stopPing: function() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    },

    /**
     * Подписка на события
     */
    on: function(event, callback) {
        if (!this.messageHandlers[event]) {
            this.messageHandlers[event] = [];
        }
        this.messageHandlers[event].push(callback);
    },

    /**
     * Отписка от событий
     */
    off: function(event, callback) {
        if (this.messageHandlers[event]) {
            var handlers = this.messageHandlers[event];
            var index = handlers.indexOf(callback);
            if (index !== -1) {
                handlers.splice(index, 1);
            }
        }
    },

    /**
     * Вызов обработчиков
     */
    _emit: function(event, data) {
        if (this.messageHandlers[event]) {
            var handlers = this.messageHandlers[event];
            for (var i = 0; i < handlers.length; i++) {
                try {
                    handlers[i](data);
                } catch (e) {
                    console.error('❌ Ошибка в обработчике ' + event + ':', e);
                }
            }
        }
    },

    /**
     * Закрытие соединения
     */
    disconnect: function() {
        this._stopPing();
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.isConnected = false;
    }
};

// Создаём глобальный экземпляр
var wsManager = WebSocketManager;