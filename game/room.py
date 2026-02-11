"""Модуль для управления игровыми комнатами"""

import uuid
import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class GameRoom:
    """Класс для управления игровой комнатой"""
    
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.created_at = datetime.now()
        self.game_state = self._create_game_state()
        self.players: Dict[int, Dict] = {}
        self.ws_connections: List = []
        self.captains: Dict[str, int] = {'red': None, 'blue': None}
    
    def _create_game_state(self) -> Dict:
        """Создаёт начальное состояние игры"""
        words = self._load_words()
        
        # Создаем ключевую карту: 9 красных, 8 синих, 1 чёрный, 7 нейтральных
        colors = (['red'] * 9) + (['blue'] * 8) + ['black'] + (['neutral'] * 7)
        random.shuffle(colors)
        
        return {
            'words': random.sample(words, 25),
            'colors': colors,
            'revealed': [False] * 25,
            'current_team': 'red',
            'current_turn': 1,
            'red_score': 9,
            'blue_score': 8,
            'game_status': 'waiting',
            'winner': None,
            'last_action': None
        }
    
    def _load_words(self) -> List[str]:
        """Загружает список слов"""
        try:
            with open('words.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return self._get_default_words()
    
    def _get_default_words(self) -> List[str]:
        """Резервный список слов"""
        return [
            "яблоко", "гора", "мост", "врач", "луна", "книга", "огонь", "река", "часы",
            "снег", "глаз", "дом", "змея", "кольцо", "корабль", "лев", "лес", "машина",
            # ... остальные слова
        ]
    
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
        
        # Если выбрана роль капитана и команда свободна
        if role == 'captain' and self.captains[team] is None:
            self.captains[team] = user_id
        
        return player_data
    
    def _assign_team(self) -> str:
        """Распределяет игрока по командам"""
        red_count = sum(1 for p in self.players.values() if p['team'] == 'red')
        blue_count = sum(1 for p in self.players.values() if p['team'] == 'blue')
        return 'red' if red_count <= blue_count else 'blue'
    
    def set_captain(self, team: str, user_id: int) -> bool:
        """Назначает капитана команды"""
        if team not in ['red', 'blue'] or user_id not in self.players:
            return False
        
        self.captains[team] = user_id
        self.players[user_id]['role'] = 'captain'
        self.players[user_id]['team'] = team
        return True
    
    def get_game_state_for_player(self, user_id: int) -> Dict:
        """Возвращает состояние игры для конкретного игрока"""
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
            'captains': {
                'red': self.captains['red'] is not None,
                'blue': self.captains['blue'] is not None
            },
            'user_role': 'agent',  # По умолчанию
            'user_team': None
        }
        
        # Добавляем информацию о пользователе
        if user_id in self.players:
            player = self.players[user_id]
            base_state['user_role'] = player['role']
            base_state['user_team'] = player['team']
            
            # Капитанам показываем цвета сразу
            if player['role'] == 'captain':
                base_state['colors'] = self.game_state['colors']
        
        return base_state
    
    def reveal_card(self, index: int, user_id: int) -> Dict:
        """Открывает карточку и обновляет состояние игры"""
        if not (0 <= index < 25):
            return {'error': 'Invalid index'}
        
        if self.game_state['revealed'][index]:
            return {'error': 'Card already revealed'}
        
        color = self.game_state['colors'][index]
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
        
        # Проверяем условия победы
        result = self._check_winner(color)
        if result['game_over']:
            self.game_state['game_status'] = 'finished'
            self.game_state['winner'] = result['winner']
        
        return {
            'index': index,
            'color': color,
            'game_state': self.get_game_state_for_player(user_id),
            'game_over': result['game_over'],
            'winner': result['winner']
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
    
    def is_active(self) -> bool:
        """Проверяет, активна ли комната"""
        return datetime.now() - self.created_at < timedelta(hours=24)
    
    def cleanup(self) -> None:
        """Очищает ресурсы комнаты"""
        for ws in self.ws_connections:
            if hasattr(ws, 'closed') and not ws.closed:
                import asyncio
                asyncio.create_task(ws.close())
        self.ws_connections.clear()