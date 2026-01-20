from fastapi import FastAPI, HTTPException
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import logging
import re
import datetime
from dotenv import load_dotenv

# Models and Logic
from models import Restaurant
from dsa import RestaurantManager
from data_loader import load_data
from history import ConversationManager

# Google Gemini
import google.generativeai as genai

# Load env
load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Trigger Reload 2
# Setup App
app = FastAPI(title="Peshawar Restaurant Chatbot API")

# Serve Frontend Static Files
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
manager: Optional[RestaurantManager] = None
conversation_manager = ConversationManager()

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AVAILABLE_MODELS = []
PREFERRED_ORDER = [
    "models/gemini-1.5-flash",
    "models/gemini-1.5-flash-latest",
    "models/gemini-1.5-flash-001",
    "models/gemini-1.5-flash-002",
    "models/gemini-1.5-pro",
    "models/gemini-1.5-pro-latest",
    "models/gemini-1.5-pro-001",
    "models/gemini-pro",
    "models/gemini-1.0-pro"
]

@app.on_event("startup")
def startup_event():
    global manager, AVAILABLE_MODELS
    
    # 1. Load Data
    data_path = os.path.join(os.path.dirname(__file__), "data", "restaurants_data.json")
    if os.path.exists(data_path):
        restaurants = load_data(data_path)
        manager = RestaurantManager(restaurants)
        logger.info(f"Loaded {len(restaurants)} restaurants.")
    else:
        logger.error(f"Data file not found at {data_path}")

    # 2. Configure Gemini & Discover Models
    if GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            logger.info("Gemini SDK Configured. Discovering available models...")
            
            # DYNAMIC MODEL DISCOVERY
            found_models = []
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        found_models.append(m.name)
                
                logger.info(f"API Returned Models: {found_models}")
                
                # Sort found models based on our preference list
                for pref in PREFERRED_ORDER:
                    if pref in found_models:
                        AVAILABLE_MODELS.append(pref)
                
                # Add fallbacks
                for m in found_models:
                    if m not in AVAILABLE_MODELS:
                        AVAILABLE_MODELS.append(m)
                        
                logger.info(f"Final Validated Model List: {AVAILABLE_MODELS}")
                
            except Exception as e:
                logger.error(f"Failed to list models: {e}")
                # Fallback to defaults
                AVAILABLE_MODELS.extend(["models/gemini-1.5-flash", "models/gemini-pro"])

        except Exception as e:
            logger.error(f"Error configuring Gemini SDK: {e}")
    else:
        logger.warning("GEMINI_API_KEY not found. Please set it in .env")

# --- PERSONA DEFINITION ---
# --- PERSONA DEFINITION ---
INZAGHI_SYSTEM_PROMPT = """
You are Inzaghi, a smart, local food assistant focused on Peshawar, Pakistan.
Your job is to recommend food, restaurants, and street food based on user mood, budget, time, and location.

🚫 FORMATTING RULES (CRITICAL - READ CAREFULLY)
- ABSOLUTELY NO ASTERISKS (*) allowed in the output.
- Do NOT use markdown bolding (like **text**). It looks ugly in the chat.
- Do NOT use markdown lists (like * item). Use dashes (-) or emojis (👉, 🔸).
- If you want to emphasize a restaurant name, write it in CAPS or just keep it normal.
- Treat the output like a WhatsApp message, not a document.

🕊️ Personality (Gen Z + Desi + Savage)
You are Inzaghi, the "Peshawar ka Food Guide".
- Vibe: Friendly but honest. Like a close friend who roasts you but still helps you.
- Slang: "Scene", "Heavy", "Level hai", "Bro", "Yaar", "Chaska", "Clown moment".

🔥 ROASTING MODE (BALANCED)
If the user asks for something basic (McDonalds) or unrealistic:
1.  **Light Roast First**: Make a joke about their choice.
2.  **ALWAYS ANSWER**: After the joke, you MUST provide the actual information or a better local alternative.
    - BAD: "McDonalds? Bhag jao." (Rude, unhelpful)
    - GOOD: "McDonalds? Peshawar aa ke frozen burger khaoge? 🤡 Khair, agar zidd hai to Saddar main hai, lekin is se behtar Fuego ka fresh burger try karo."

🌍 Language Handling
- Mix Urdu/English/Pashto naturally.

📍 Location Focus
Prioritize Peshawar.

💸 Budget Awareness
- Cheap: "Jaib pe halka."
- Expensive: "Ameeron wali vibes."

🎯 Core Goal
Roast the bad choices, but ALWAYS guide them to good food. Never leave them empty-handed.
"""

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

class ChatResponse(BaseModel):
    response: str
    suggestions: List[Restaurant] = []

def get_relevant_candidates(message: str, manager: RestaurantManager) -> List[Restaurant]:
    """
    Heuristic to find relevant restaurants to feed as context to LLM.
    """
    msg_lower = message.lower()
    candidates = {}

    # 1. Budget Search
    budget_match = re.search(r'(\d+)', msg_lower)
    if budget_match:
        amount = int(budget_match.group(1))
        # Get items under budget
        items = manager.search_items_by_budget(amount)
        # Add their restaurants
        for item_res in items[:10]: # Limit to top 10 cheapest relevant
            r = item_res['restaurant']
            candidates[r.id] = r
            
    # 2. Location Search
    loc_results = manager.search_by_location(message)
    for r in loc_results:
        candidates[r.id] = r

    # 3. Menu/Cuisine Search
    menu_results = manager.search_by_menu(message)
    for r in menu_results:
        candidates[r.id] = r
        
    # 4. Name Search
    # Only if message length is short to avoid noise
    if len(message.split()) < 5:
         name_results = manager.search_by_name(message)
         for r in name_results:
             candidates[r.id] = r
    
    return list(candidates.values())

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not manager:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    user_msg = request.message
    conversation_manager.add_message("user", user_msg)
    
    # Get Time
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    
    # 1. Identify Context Candidates (RAG)
    candidates = get_relevant_candidates(user_msg, manager)
    
    # Limit candidates
    candidates = candidates[:15]
    
    # Format Context for LLM
    context_text = "Here is the list of available restaurants in our database matching the query:\n"
    if candidates:
        for r in candidates:
            menu_sample = ", ".join([f"{m.item} ({m.price})" for m in r.menu[:5]])
            context_text += f"- Name: {r.name}\n  Location: {r.location}\n  Budget: {r.budget}\n  Cuisine: {', '.join(r.cuisine)}\n  Deals: {r.deals}\n  Menu Sample: {menu_sample}\n\n"
    else:
        context_text += "No specific restaurants found directly matching keywords in the database. Rely on your internal knowledge or ask clarifying questions.\n"

    # 2. Prepare History
    history_tuples = conversation_manager.get_history()
    # Take last 10 interactions (20 messages approx)
    recent_history = history_tuples[-10:] 
    history_text = ""
    for role, msg in recent_history:
        history_text += f"{role.capitalize()}: {msg}\n"

    # 3. Generate Response
    response_text = ""
    
    if GEMINI_API_KEY:
        try:
            full_prompt = f"{INZAGHI_SYSTEM_PROMPT}\n\nContext Information:\nCurrent Time: {current_time}\n{context_text}\n\nConversation History:\n{history_text}\n\nUser Message: {user_msg}\n\nResponse:"
            
            # Use the dynamically validated list
            if not AVAILABLE_MODELS:
                response_text = "Maaf ka! No AI models are currently available to me."
            else:
                last_error = None
                import time
                
                # Try every validated model in order
                for model_name in AVAILABLE_MODELS:
                    # Retry each model up to 2 times
                    for attempt in range(2):
                        try:
                            logger.info(f"Attempting to generate with model: {model_name} (Attempt {attempt+1})")
                            model = genai.GenerativeModel(model_name)
                            llm_response = model.generate_content(full_prompt)
                            response_text = llm_response.text
                            break # Success
                        except Exception as e:
                            error_str = str(e)
                            last_error = e
                            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                                logger.warning(f"Rate Limit hit on {model_name}. Waiting 5s...")
                                time.sleep(5)
                                continue
                            
                            logger.warning(f"Failed with model {model_name}: {e}")
                            break # Move to next model
                    
                    if response_text:
                        break # Success
                
                if not response_text and last_error:
                    raise last_error
                
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            response_text = f"Maaf ka! I'm having trouble thinking right now. (Error: {str(e)})"
    else:
        response_text = "Gemini API Key is missing! I need it to wake up."

    # 3. Save Context & History
    conversation_manager.add_message("bot", response_text)
    
    return ChatResponse(response=response_text, suggestions=candidates)


# Catch-all route to serve index.html for SPA (must be last)
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    return FileResponse("static/index.html")
