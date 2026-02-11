// ==================== УТИЛИТЫ ====================

/**
 * Получение параметров URL
 */
function getUrlParams() {
    var params = new URLSearchParams(window.location.search);
    return {
        roomId: params.get('room') ? params.get('room').toUpperCase() : null,
        role: params.get('role') || 'agent'
    };
}

/**
 * Копирование текста в буфер обмена
 */
function copyToClipboard(text) {
    try {
        navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        // Резервный метод
        var textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        return true;
    }
}

/**
 * Форматирование времени
 */
function formatTime(seconds) {
    var mins = Math.floor(seconds / 60);
    var secs = seconds % 60;
    return mins + ':' + (secs < 10 ? '0' + secs : secs);
}

/**
 * Debounce для оптимизации
 */
function debounce(func, wait) {
    var timeout;
    return function() {
        var context = this;
        var args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(function() {
            func.apply(context, args);
        }, wait);
    };
}

/**
 * Генерация цвета команды
 */
function getTeamColor(team) {
    switch (team) {
        case 'red': return '#f87171';
        case 'blue': return '#60a5fa';
        case 'black': return '#000000';
        default: return '#d97706';
    }
}

/**
 * Экранирование HTML
 */
function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}