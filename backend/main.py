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

# Serve Frontend Static Files
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

# Catch-all route removed from here to place at the end 


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
            logger.info("Gemini Client Initialized.")
            
            # Prefer a specific stable version to avoid alias issues in some environments
            GEMINI_MODEL_NAME = "gemini-1.5-flash" 
            
        except Exception as e:
            logger.error(f"Error configuring Gemini Client: {e}")
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
            
            # List of models to try in order of preference
            models_to_try = [
                GEMINI_MODEL_NAME,      # Default
                "gemini-1.5-flash-002", # Newer
                "gemini-1.5-flash-001", # Stable
                "gemini-1.5-pro",       # Pro version
                "gemini-pro",           # 1.0 Pro (Most stable fallback)
            ]
            
            last_error = None
            
            import time
            
            for model in models_to_try:
                # Retry each model up to 2 times if we get a 429 (Rate Limit)
                for attempt in range(2):
                    try:
                        logger.info(f"Attempting to generate with model: {model} (Attempt {attempt+1})")
                        llm_response = client.models.generate_content(
                            model=model,
                            contents=full_prompt
                        )
                        response_text = llm_response.text
                        break # Success, break inner loop
                    except Exception as e:
                        error_str = str(e)
                        last_error = e
                        
                        # Check for Rate Limit (429) or Resource Exhausted
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                            logger.warning(f"Rate Limit hit on {model}. Waiting 5s...")
                            time.sleep(5)
                            continue # Retry same model
                        
                        # If 404 or other error, break inner loop and move to next model
                        logger.warning(f"Failed with model {model}: {e}")
                        break
                
                if response_text:
                    break # Success, break outer loop (model list)
            
            if not response_text and last_error:
                raise last_error # Re-raise if all failed
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            response_text = f"Maaf ka! I'm having trouble thinking right now. (Error: {str(e)})"
    else:
        response_text = "Gemini API Key is missing or Client failed! I need it to wake up."

    # 3. Save Context & History
    conversation_manager.add_message("bot", response_text)
    
    return ChatResponse(response=response_text, suggestions=candidates)


# Catch-all route to serve index.html for SPA (must be last)
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    return FileResponse("static/index.html")
