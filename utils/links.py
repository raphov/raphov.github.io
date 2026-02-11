# utils/links.py
from .config import FRONTEND_URL

def make_game_link(room_id: str, user_id: int) -> str:
    return f"{FRONTEND_URL}?room={room_id}&user_id={user_id}"