"""
Модуль для управления игровой комнатой Codenames
Версия 3.0 - Полная логика игры
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Глобальное хранилище активных комнат
active_rooms: Dict[str, 'GameRoom'] = {}


class GameRoom:
    """Класс для управления игровой комнатой"""

    def __init__(self, room_id: str):
        self.room_id = room_id
        self.created_at = datetime.now()
        self.game_state = self._create_game_state()
        self.players: Dict[int, Dict] = {}  # user_id -> player_data
        self.ws_connections: List = []       # WebSocket соединения
        self.captains: Dict[str, Optional[int]] = {'red': None, 'blue': None}

    def _create_game_state(self) -> Dict:
        """Создаёт начальное состояние игры"""
        words = self._load_words()
        
        # Стандартная колода Codenames: 9 красных, 8 синих, 1 чёрный, 7 нейтральных
        colors = (['red'] * 9) + (['blue'] * 8) + ['black'] + (['neutral'] * 7)
        random.shuffle(colors)
        
        return {
            'words': random.sample(words, 25),
            'colors': colors,
            'revealed': [False] * 25,
            'current_team': 'red',      # Красные ходят первыми
            'current_turn': 1,
            'red_score': 9,
            'blue_score': 8,
            'game_status': 'waiting',    # waiting, active, finished
            'winner': None,
            'last_action': None,
            'hint': None,               # Текущая подсказка капитана
            'hint_number': None,        # Количество слов в подсказке
            'guesses_left': 0           # Сколько ещё можно угадать
        }

    def _load_words(self) -> List[str]:
        """Загружает список слов из файла или использует резервный"""
        try:
            with open('words.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # Резервный список русских слов
            return [
                "яблоко", "гора", "мост", "врач", "луна", "книга", "огонь", "река", "часы",
                "снег", "глаз", "дом", "змея", "кольцо", "корабль", "лев", "лес", "машина",
                "медведь", "нос", "океан", "перо", "пила", "поле", "пуля", "работа", "роза",
                "рука", "сапог", "сок", "стол", "театр", "тень", "фонтан", "хлеб", "школа",
                "шляпа", "ящик", "игла", "йогурт", "зонт", "ксерокс", "эхо", "юла", "якорь",
                "аэропорт", "балерина", "вентилятор", "градусник", "дерево", "ёжик", "железо",
                "замок", "игрушка", "капуста", "лампа", "метро", "ноутбук", "облако", "пальто",
                "ракета", "самолет", "телефон", "улица", "фонарь", "хоккей", "цветок", "человек",
                "шапка", "щука", "экран", "юбка", "язык", "аптека", "бензин", "велосипед", "газета"
            ]

    # ==================== УПРАВЛЕНИЕ ИГРОКАМИ ====================

    def add_player(self, user_id: int, username: str, role: str = 'agent') -> Dict:
        """Добавляет игрока в комнату"""
        team = self._assign_team()
        player_data = {
            'id': user_id,
            'username': username,
            'role': role,
            'team': team,
            'joined_at': datetime.now(),
            'is_online': True
        }
        self.players[user_id] = player_data
        return player_data

    def _assign_team(self) -> str:
        """Распределяет игрока по командам для баланса"""
        red_count = sum(1 for p in self.players.values() if p['team'] == 'red')
        blue_count = sum(1 for p in self.players.values() if p['team'] == 'blue')
        return 'red' if red_count <= blue_count else 'blue'

    def remove_player(self, user_id: int) -> bool:
        """Удаляет игрока из комнаты"""
        if user_id in self.players:
            # Если игрок был капитаном, освобождаем место
            if self.captains['red'] == user_id:
                self.captains['red'] = None
            if self.captains['blue'] == user_id:
                self.captains['blue'] = None
            
            del self.players[user_id]
            return True
        return False

    def set_captain(self, team: str, user_id: int) -> bool:
        """Назначает капитана команды"""
        if team not in ['red', 'blue']:
            return False
        
        if user_id not in self.players:
            return False
        
        self.captains[team] = user_id
        self.players[user_id]['role'] = 'captain'
        self.players[user_id]['team'] = team
        return True

    def get_player_team(self, user_id: int) -> Optional[str]:
        """Возвращает команду игрока"""
        if user_id in self.players:
            return self.players[user_id]['team']
        return None

    def get_player_role(self, user_id: int) -> Optional[str]:
        """Возвращает роль игрока"""
        if user_id in self.players:
            return self.players[user_id]['role']
        return None

    def is_captain(self, user_id: int) -> bool:
        """Проверяет, является ли игрок капитаном"""
        return user_id in (self.captains['red'], self.captains['blue'])

    # ==================== СОСТОЯНИЕ ИГРЫ ДЛЯ КЛИЕНТА ====================

    def get_game_state_for_player(self, user_id: int) -> Dict:
        """
        Возвращает состояние игры для конкретного игрока
        Капитаны видят цвета, агенты - нет
        """
        base_state = {
            'room_id': self.room_id,
            'words': self.game_state['words'],
            'revealed': self.game_state['revealed'],
            'current_team': self.game_state['current_team'],
            'current_turn': self.game_state['current_turn'],
            'red_score': self.game_state['red_score'],
            'blue_score': self.game_state['blue_score'],
            'game_status': self.game_state['game_status'],
            'winner': self.game_state['winner'],
            'players_count': len(self.players),
            'user_role': self.players.get(user_id, {}).get('role', 'agent'),
            'user_team': self.players.get(user_id, {}).get('team'),
            'captains': {
                'red': self.captains['red'] is not None,
                'blue': self.captains['blue'] is not None
            }
        }
        
        # Капитанам добавляем цвета карточек
        if self.is_captain(user_id):
            base_state['colors'] = self.game_state['colors']
        
        return base_state

    def get_public_state(self) -> Dict:
        """
        Возвращает публичное состояние игры (без user_id)
        Используется для рассылки всем игрокам
        """
        return {
            'room_id': self.room_id,
            'words': self.game_state['words'],
            'revealed': self.game_state['revealed'],
            'current_team': self.game_state['current_team'],
            'current_turn': self.game_state['current_turn'],
            'red_score': self.game_state['red_score'],
            'blue_score': self.game_state['blue_score'],
            'game_status': self.game_state['game_status'],
            'winner': self.game_state['winner'],
            'players_count': len(self.players),
            'captains': {
                'red': self.captains['red'] is not None,
                'blue': self.captains['blue'] is not None
            }
        }

    # ==================== ИГРОВАЯ ЛОГИКА ====================

    def reveal_card(self, index: int, user_id: int) -> Dict:
        """
        Открывает карточку и обновляет состояние игры
        Возвращает результат для обработки в WebSocket
        """
        # Проверка индекса
        if not (0 <= index < 25):
            return {'error': 'Invalid card index'}
        
        # Проверка, что карта ещё не открыта
        if self.game_state['revealed'][index]:
            return {'error': 'Card already revealed'}
        
        # Проверка, что игра активна
        if self.game_state['game_status'] != 'active':
            return {'error': 'Game is not active'}
        
        # Проверка, что игрок в правильной команде
        player_team = self.get_player_team(user_id)
        if player_team != self.game_state['current_team']:
            return {'error': 'Not your team\'s turn'}
        
        # Получаем цвет карты
        color = self.game_state['colors'][index]
        
        # Открываем карту
        self.game_state['revealed'][index] = True
        self.game_state['last_action'] = {
            'type': 'card_revealed',
            'index': index,
            'color': color,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        }
        
        # Обновляем счёт
        if color == 'red':
            self.game_state['red_score'] = max(0, self.game_state['red_score'] - 1)
        elif color == 'blue':
            self.game_state['blue_score'] = max(0, self.game_state['blue_score'] - 1)
        
        # Уменьшаем количество оставшихся попыток, если есть подсказка
        if self.game_state['guesses_left'] > 0:
            self.game_state['guesses_left'] -= 1
        
        # Проверяем условия победы
        winner_check = self._check_winner(color)
        game_over = winner_check['game_over']
        winner = winner_check['winner']
        
        if game_over:
            self.game_state['game_status'] = 'finished'
            self.game_state['winner'] = winner
        
        return {
            'index': index,
            'color': color,
            'game_state': self.get_game_state_for_player(user_id),
            'game_over': game_over,
            'winner': winner
        }

    def _check_winner(self, last_color: str) -> Dict:
        """Проверяет условия завершения игры"""
        game = self.game_state
        
        # Если открыли чёрную карточку
        if last_color == 'black':
            winner = 'blue' if game['current_team'] == 'red' else 'red'
            return {'game_over': True, 'winner': winner, 'reason': 'assassin'}
        
        # Если одна из команд открыла все свои карточки
        if game['red_score'] == 0:
            return {'game_over': True, 'winner': 'red', 'reason': 'all_found'}
        if game['blue_score'] == 0:
            return {'game_over': True, 'winner': 'blue', 'reason': 'all_found'}
        
        return {'game_over': False, 'winner': None, 'reason': None}

    def switch_team(self) -> None:
        """Переключает текущую команду"""
        self.game_state['current_team'] = 'blue' if self.game_state['current_team'] == 'red' else 'red'
        self.game_state['current_turn'] += 1
        self.game_state['guesses_left'] = 0  # Сбрасываем количество попыток
        self.game_state['hint'] = None
        self.game_state['hint_number'] = None

    def set_hint(self, hint_word: str, hint_number: int) -> bool:
        """
        Капитан даёт подсказку
        Количество попыток = hint_number + 1
        """
        if hint_number < 0 or hint_number > 9:
            return False
        
        self.game_state['hint'] = hint_word
        self.game_state['hint_number'] = hint_number
        self.game_state['guesses_left'] = hint_number + 1  # Можно угадать N+1 слов
        return True

    def end_turn(self) -> None:
        """Принудительное завершение хода"""
        self.switch_team()

    def pass_turn(self) -> None:
        """Передача хода (пас)"""
        self.switch_team()

    # ==================== УПРАВЛЕНИЕ КОМНАТОЙ ====================

    def start_game(self) -> bool:
        """Начинает игру (если есть оба капитана)"""
        if self.captains['red'] is not None and self.captains['blue'] is not None:
            self.game_state['game_status'] = 'active'
            return True
        return False

    def reset_game(self) -> None:
        """Сбрасывает игру, оставляя игроков в комнате"""
        self.game_state = self._create_game_state()
        # Пересохраняем капитанов
        for team, captain_id in self.captains.items():
            if captain_id and captain_id in self.players:
                self.players[captain_id]['role'] = 'captain'
                self.players[captain_id]['team'] = team

    def is_active(self) -> bool:
        """Проверяет, активна ли комната (не старше 24 часов)"""
        return datetime.now() - self.created_at < timedelta(hours=24)

    def cleanup(self) -> None:
        """Очищает ресурсы комнаты"""
        import asyncio
        for ws in self.ws_connections:
            if hasattr(ws, 'closed') and not ws.closed:
                asyncio.create_task(ws.close())
        self.ws_connections.clear()
        self.players.clear()
        self.captains = {'red': None, 'blue': None}

    # ==================== СТАТИСТИКА И ИНФОРМАЦИЯ ====================

    def get_stats(self) -> Dict:
        """Возвращает статистику комнаты"""
        revealed_count = sum(1 for r in self.game_state['revealed'] if r)
        red_found = 9 - self.game_state['red_score']
        blue_found = 8 - self.game_state['blue_score']
        
        return {
            'room_id': self.room_id,
            'created_at': self.created_at.isoformat(),
            'age_minutes': (datetime.now() - self.created_at).seconds // 60,
            'players': len(self.players),
            'connections': len(self.ws_connections),
            'game_status': self.game_state['game_status'],
            'current_team': self.game_state['current_team'],
            'current_turn': self.game_state['current_turn'],
            'revealed_cards': revealed_count,
            'red_found': red_found,
            'blue_found': blue_found,
            'red_left': self.game_state['red_score'],
            'blue_left': self.game_state['blue_score'],
            'captains': {
                'red': self.captains['red'] is not None,
                'blue': self.captains['blue'] is not None
            }
        }

    def to_dict(self) -> Dict:
        """Сериализация комнаты для отладки"""
        return {
            'room_id': self.room_id,
            'created_at': self.created_at.isoformat(),
            'players': [
                {
                    'id': p['id'],
                    'username': p['username'],
                    'role': p['role'],
                    'team': p['team']
                } for p in self.players.values()
            ],
            'captains': {
                'red': self.captains['red'],
                'blue': self.captains['blue']
            },
            'game_status': self.game_state['game_status'],
            'winner': self.game_state['winner'],
            'red_score': self.game_state['red_score'],
            'blue_score': self.game_state['blue_score'],
            'current_team': self.game_state['current_team'],
            'current_turn': self.game_state['current_turn']
        }