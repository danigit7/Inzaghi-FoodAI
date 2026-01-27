from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import logging
import re
import datetime
from dotenv import load_dotenv

from models import Restaurant
from dsa import RestaurantManager
from data_loader import load_data
from history import SessionStore

import google.generativeai as genai

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Peshawar Restaurant Chatbot API")

static_dir = os.path.join(os.path.dirname(__file__), "static")
assets_dir = os.path.join(static_dir, "assets")
sessions_dir = os.path.join(os.path.dirname(__file__), "data", "sessions")
os.makedirs(assets_dir, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager: Optional[RestaurantManager] = None
session_store: Optional[SessionStore] = None
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
model = None

INZAGHI_SYSTEM_PROMPT = """
You are Inzaghi, a friendly, local "Peshawari" food enthusiast and AI guide.
Your goal is to help users find the best restaurants in Peshawar based on their cravings, budget, and location.

Personality:
- Friendly, warm, and inviting.
- Uses local Peshawari slang occasionally (e.g., "Yaara", "Kha", "Zabardast", "Maaf ka").
- Loves food and talks about it passionately.
- Honest about prices and quality.

Instructions:
- Use the provided context to answer questions.
- If the context matches the user's query, recommend those restaurants.
- If the context is empty or irrelevant, admit you don't know and ask for more details.
- Always mention the price/budget if available.
- Be concise but helpful.

Formatting:
- Use '•' (unicode bullet) for all list items. Do NOT use '*'.
- Use plain text, avoid markdown formatting like **bold** or *italics*.
- Capitalize restaurant names for emphasis instead of bolding.
"""

@app.on_event("startup")
def startup_event():
    global manager, model, session_store
    
    try:
        data_path = os.path.join(os.path.dirname(__file__), "data", "restaurants_data.json")
        if os.path.exists(data_path):
            try:
                restaurants = load_data(data_path)
                manager = RestaurantManager(restaurants)
                logger.info(f"Loaded {len(restaurants)} restaurants.")
            except Exception as e:
                logger.error(f"Error loading restaurant data: {e}")
                # Don't crash, just let manager be None or handle gracefully
        else:
            logger.error(f"Data file not found at {data_path}")

        try:
            session_store = SessionStore(sessions_dir, session_expiry_hours=24)
            logger.info(f"SessionStore initialized with {len(session_store.sessions)} existing sessions.")
        except Exception as e:
            logger.error(f"Error initializing SessionStore: {e}")
            # Fallback to in-memory only or tmp dir?
            # For now, let's log it.

        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            try:
                found_model_name = None
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        if 'flash' in m.name:
                            found_model_name = m.name
                            break
                
                if not found_model_name:
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            found_model_name = m.name
                            break
                
                if found_model_name:
                    logger.info(f"Using Gemini Model: {found_model_name}")
                    model = genai.GenerativeModel(found_model_name)
                else:
                    logger.error("No suitable Gemini model found.")
            except Exception as e:
                logger.error(f"Error configuring Gemini: {e}")
                model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            logger.warning("GEMINI_API_KEY not found. Please set it in .env")
            
    except Exception as e:
        logger.critical(f"Critical error during startup: {e}")

@app.get("/health")
def health_check():
    return {"status": "ok", "manager_loaded": manager is not None, "model_loaded": model is not None}


@app.get("/search/name", response_model=List[Restaurant])
def search_by_name(q: str):
    if not manager: raise HTTPException(503, "Service not ready")
    return manager.search_by_name(q)

@app.get("/search/menu", response_model=List[Restaurant])
def search_by_menu(q: str):
    if not manager: raise HTTPException(503, "Service not ready")
    return manager.search_by_menu(q)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    suggestions: List[Restaurant] = []
    session_id: str

class SessionResponse(BaseModel):
    session_id: str

class HistoryResponse(BaseModel):
    session_id: str
    history: List[Dict[str, str]]

@app.post("/session/new", response_model=SessionResponse)
def create_new_session():
    if not session_store:
        raise HTTPException(status_code=503, detail="Service not ready")
    new_id = session_store.create_session()
    return SessionResponse(session_id=new_id)

@app.get("/session/{session_id}/history", response_model=HistoryResponse)
def get_session_history(session_id: str):
    if not session_store:
        raise HTTPException(status_code=503, detail="Service not ready")
    if not session_store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    history = session_store.get_history(session_id)
    return HistoryResponse(session_id=session_id, history=history)

def get_relevant_candidates(message: str, manager: RestaurantManager) -> List[Restaurant]:
    msg_lower = message.lower()
    candidates = {}

    budget_match = re.search(r'(\d+)', msg_lower)
    if budget_match:
        amount = int(budget_match.group(1))
        items = manager.search_items_by_budget(amount)
        for item_res in items[:10]:
            r = item_res['restaurant']
            candidates[r.id] = r
            
    loc_results = manager.search_by_location(message)
    for r in loc_results:
        candidates[r.id] = r

    menu_results = manager.search_by_menu(message)
    for r in menu_results:
        candidates[r.id] = r
        
    if len(message.split()) < 5:
        name_results = manager.search_by_name(message)
        for r in name_results:
            candidates[r.id] = r
    
    return list(candidates.values())

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not manager or not session_store:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    session_id = session_store.get_or_create_session(request.session_id)
    user_msg = request.message
    session_store.add_message(session_id, "user", user_msg)
    
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    candidates = get_relevant_candidates(user_msg, manager)
    candidates = candidates[:15]
    
    context_text = "Here is the list of available restaurants in our database matching the query:\n"
    if candidates:
        for r in candidates:
            menu_sample = ", ".join([f"{m.item} ({m.price})" for m in r.menu[:5]])
            context_text += f"- Name: {r.name}\n  Location: {r.location}\n  Budget: {r.budget}\n  Cuisine: {', '.join(r.cuisine)}\n  Deals: {r.deals}\n  Menu Sample: {menu_sample}\n\n"
    else:
        context_text += "No specific restaurants found directly matching keywords in the database. Rely on your internal knowledge or ask clarifying questions.\n"

    response_text = ""
    
    if model:
        try:
            full_prompt = f"{INZAGHI_SYSTEM_PROMPT}\n\nContext Information:\nCurrent Time: {current_time}\n{context_text}\n\nUser Message: {user_msg}\n\nResponse:"
            llm_response = await model.generate_content_async(full_prompt)
            response_text = llm_response.text
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            response_text = f"Maaf ka! I'm having trouble thinking right now. (Error: {str(e)})"
    else:
        response_text = "Gemini API Key is missing! I need it to wake up."

    session_store.add_message(session_id, "bot", response_text)
    
    return ChatResponse(response=response_text, suggestions=candidates, session_id=session_id)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

