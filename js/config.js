// ==================== КОНФИГУРАЦИЯ ====================
const CONFIG = {
    RENDER_URL: 'codenames-u88n.onrender.com',
    HOLD_DURATION: 1200, 
    VERSION: '3.1.0',
    MAX_RECONNECT_ATTEMPTS: 5,
    PING_INTERVAL: 30000,
    ROOM_LIFETIME: 24 * 60 * 60 * 1000
};

const TEAMS = {
    RED: 'red',
    BLUE: 'blue',
    BLACK: 'black',
    NEUTRAL: 'neutral'
};

const TEAM_NAMES = {
    red: 'Красные',
    blue: 'Синие',
    black: 'Убийца',
    neutral: 'Нейтральные'
};

const ROLES = {
    CAPTAIN: 'captain',
    AGENT: 'agent'
};

const GAME_STATUS = {
    WAITING: 'waiting',
    ACTIVE: 'active',
    FINISHED: 'finished'
};