from typing import List, Dict, Tuple, Optional
from models import Restaurant
import os
import json
import uuid
from datetime import datetime, timedelta
import threading


class SessionStore:
    def __init__(self, storage_dir: str, session_expiry_hours: int = 24, history_limit: int = 10):
        self.storage_dir = storage_dir
        self.session_expiry_hours = session_expiry_hours
        self.history_limit = history_limit
        self.sessions: Dict[str, dict] = {}
        self.lock = threading.Lock()
        
        try:
            os.makedirs(storage_dir, exist_ok=True)
        except PermissionError:

            import tempfile
            self.storage_dir = os.path.join(tempfile.gettempdir(), "sessions")
            os.makedirs(self.storage_dir, exist_ok=True)
        except Exception:
            pass
        self._load_sessions()
        self._cleanup_expired()
    
    def _load_sessions(self):
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.storage_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                        session_id = session_data.get('session_id')
                        if session_id:
                            self.sessions[session_id] = session_data
                except Exception:
                    pass
    
    def _save_session(self, session_id: str):
        if session_id not in self.sessions:
            return
        filepath = os.path.join(self.storage_dir, f"{session_id}.json")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.sessions[session_id], f, indent=2, default=str)
        except Exception:
            pass
    
    def _cleanup_expired(self):
        now = datetime.now()
        expired = []
        for session_id, data in self.sessions.items():
            last_active = data.get('last_active')
            if isinstance(last_active, str):
                try:
                    last_active = datetime.fromisoformat(last_active)
                except:
                    continue
            if last_active and (now - last_active) > timedelta(hours=self.session_expiry_hours):
                expired.append(session_id)
        
        for session_id in expired:
            self._delete_session(session_id)
    
    def _delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
        filepath = os.path.join(self.storage_dir, f"{session_id}.json")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
    
    def create_session(self) -> str:
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now()
        with self.lock:
            self.sessions[session_id] = {
                'session_id': session_id,
                'history': [],
                'created_at': now.isoformat(),
                'last_active': now.isoformat()
            }
            self._save_session(session_id)
        return session_id
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        if session_id and session_id in self.sessions:
            return session_id
        return self.create_session()
    
    def add_message(self, session_id: str, role: str, message: str):
        with self.lock:
            if session_id not in self.sessions:
                session_id = self.create_session()
            
            session = self.sessions[session_id]
            session['history'].append({'role': role, 'message': message})
            
            if len(session['history']) > self.history_limit * 2:
                session['history'] = session['history'][-self.history_limit * 2:]
            
            session['last_active'] = datetime.now().isoformat()
            self._save_session(session_id)
        return session_id
    
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        if session_id in self.sessions:
            return self.sessions[session_id].get('history', [])
        return []
    
    def get_history_tuples(self, session_id: str) -> List[Tuple[str, str]]:
        history = self.get_history(session_id)
        return [(h.get('role', ''), h.get('message', '')) for h in history]
    
    def session_exists(self, session_id: str) -> bool:
        return session_id in self.sessions
