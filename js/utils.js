// ==================== УТИЛИТЫ ====================

/**
 * Получение параметров URL
 */
function getUrlParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        roomId: params.get('room')?.toUpperCase() || null,
        userId: params.get('user_id') || null
    };
}

/**
 * Копирование текста в буфер обмена
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        // Резервный метод
        const textArea = document.createElement('textarea');
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
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Debounce для оптимизации
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
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

// ==================== ЭКСПОРТ ====================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { getUrlParams, copyToClipboard, formatTime, debounce, getTeamColor };
}