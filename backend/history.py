from typing import List, Tuple, Optional
from models import Restaurant

class ConversationManager:
    def __init__(self, history_limit: int = 3):
        self.history_limit = history_limit
        # List of (role, message) tuples. Role: "user" or "bot"
        self.history: List[Tuple[str, str]] = []
        
        # Context tracking
        self.last_mentioned_restaurants: List[Restaurant] = []
    
    def add_message(self, role: str, message: str):
        self.history.append((role, message))
        if len(self.history) > self.history_limit * 2: # Limit pairs
            self.history = self.history[-self.history_limit*2:]
            
    def set_context(self, restaurants: List[Restaurant]):
        if restaurants:
            self.last_mentioned_restaurants = restaurants
            
    def get_context(self) -> List[Restaurant]:
        return self.last_mentioned_restaurants

    def get_history(self) -> List[Tuple[str, str]]:
        return self.history

    def clear_history(self):
        self.history = []
        self.last_mentioned_restaurants = []
