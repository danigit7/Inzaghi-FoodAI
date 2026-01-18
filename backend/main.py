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
from google import genai

# Load env
load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Trigger Reload 2
# Setup App
app = FastAPI(title="Peshawar Restaurant Chatbot API")

@app.get("/")
def read_root():
    return {"message": "Inzaghi FoodieAi Backend is Running!", "docs_url": "/docs"}

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
client = None
GEMINI_MODEL_NAME = "gemini-1.5-flash"

# --- PERSONA DEFINITION ---
INZAGHI_SYSTEM_PROMPT = """
You are Inzaghi, a smart, local food assistant focused on Peshawar, Pakistan.
Your job is to recommend food, restaurants, and street food based on user mood, budget, time, and location.

🕊️ Personality
You are friendly, confident, and street-smart.
Light humor only — never forced jokes.
No overacting, no childish tone.
Sound like a local friend who knows food.
Be honest (even if food is overrated).

🌍 Language Handling (VERY IMPORTANT)
Automatically detect and respond in:
- Roman Urdu
- Roman Pashto
- English
Reply in the same language the user uses.
If mixed language is used, reply naturally in mixed tone.
Never translate unless asked.

📍 Location Focus
Prioritize Peshawar.
Mention areas like: Namak Mandi, University Road, Saddar, Charsadda Road.
If user asks outside Peshawar, politely clarify.

💸 Budget Awareness
Under 500 PKR → street food, shawarma, tikka.
Under 1000 PKR → burgers, half karahi, fast food.
Family / higher budget → proper restaurants.
Be realistic — no luxury lies.

🕒 Time-Based Logic
Late night → Namak Mandi, University Road.
Daytime → cafes, restaurants, fast food.

🧠 Response Style
Do NOT sound like Google.
Do NOT give robotic answers.
Do NOT overpraise restaurants.
Do NOT lie about food quality.
Do NOT use Hindi-style wording.

Humor should be Dry, Local, Subtle.
Example: "Diet kal se." or "Dil karahi kehta hai."

Sample Response Style:
Roman Urdu: "Budget tight hai to Charsadda Road best hai. Kam paisay, full taste. Simple."
Roman Pashto: "Namak Mandi laar sha, agha asli taste di. Baqi sab side options di."
English: "If you’re hungry and it’s late, Namak Mandi is still the safest bet."

🎯 Core Goal
Help users decide quickly what to eat without confusion, using:
Local knowledge, Budget logic, Honest opinions, Clean personality.
You are not just an assistant — you are Peshawar’s food guide.
"""

@app.on_event("startup")
def startup_event():
    global manager, client
    
    # 1. Load Data
    data_path = os.path.join(os.path.dirname(__file__), "data", "restaurants_data.json")
    if os.path.exists(data_path):
        restaurants = load_data(data_path)
        manager = RestaurantManager(restaurants)
        logger.info(f"Loaded {len(restaurants)} restaurants.")
    else:
        logger.error(f"Data file not found at {data_path}")

    # 2. Configure Gemini
    global client, GEMINI_MODEL_NAME
    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Auto-discover the best available model
            found_model_name = None
            try:
                # client.models.list returns an iterator
                for m in client.models.list():
                    # Check support methods if available, otherwise assume yes or check name
                    # The new SDK model object structure might differ, safe check:
                    if 'generateContent' in (m.supported_generation_methods or []):
                        if 'flash' in m.name:
                            found_model_name = m.name
                            break
            except Exception:
                pass # Fallback if list fails
            
            if not found_model_name:
                 # Fallback search
                 try:
                    for m in client.models.list():
                        if 'generateContent' in (m.supported_generation_methods or []):
                            found_model_name = m.name
                            break
                 except Exception:
                    pass

            if found_model_name:
                logger.info(f"Using Gemini Model: {found_model_name}")
                GEMINI_MODEL_NAME = found_model_name
            else:
                logger.info("Using default Gemini Model: gemini-1.5-flash")
                GEMINI_MODEL_NAME = "gemini-1.5-flash"
                
        except Exception as e:
            logger.error(f"Error configuring Gemini Client: {e}")
            # Client might be None if init failed, but we define global client above
    else:
        logger.warning("GEMINI_API_KEY not found. Please set it in .env")


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
    
    # If no candidates found used heuristics, but user message is very short, maybe it's "hi" or "hello"
    # We still pass empty context
    
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

    # 2. Generate Response
    response_text = ""
    
    if client:
        try:
            full_prompt = f"{INZAGHI_SYSTEM_PROMPT}\n\nContext Information:\nCurrent Time: {current_time}\n{context_text}\n\nUser Message: {user_msg}\n\nResponse:"
            
            # Generate
            llm_response = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=full_prompt
            )
            response_text = llm_response.text
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            response_text = f"Maaf ka! I'm having trouble thinking right now. (Error: {str(e)})"
    else:
        response_text = "Gemini API Key is missing or Client failed! I need it to wake up."

    # 3. Save Context & History
    conversation_manager.add_message("bot", response_text)
    
    return ChatResponse(response=response_text, suggestions=candidates)



