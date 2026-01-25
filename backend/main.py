from fastapi import FastAPI, HTTPException, Request, CORSMiddleware
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

# Mount Static Assets (Absolute Path)
static_dir = os.path.join(os.path.dirname(__file__), "static")
assets_dir = os.path.join(static_dir, "assets")

# Ensure directories exist
os.makedirs(assets_dir, exist_ok=True)

app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Logo from Root (for favicon etc)
@app.get("/logo_transparent.png")
async def serve_logo():
    logo_path = os.path.join(static_dir, "logo_transparent.png")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    # Fallback to asset if root missing
    asset_logo = os.path.join(assets_dir, "logo_transparent.png") 
    if os.path.exists(asset_logo):
        return FileResponse(asset_logo)
    return HTTPException(404, "Logo not found")

# Global State
manager: Optional[RestaurantManager] = None
conversation_manager = ConversationManager()

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
model = None # Initialized in startup

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
    global manager, model
    
    # 1. Load Data
    data_path = os.path.join(os.path.dirname(__file__), "data", "restaurants_data.json")
    if os.path.exists(data_path):
        restaurants = load_data(data_path)
        manager = RestaurantManager(restaurants)
        logger.info(f"Loaded {len(restaurants)} restaurants.")
    else:
        logger.error(f"Data file not found at {data_path}")

    # 2. Configure Gemini
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        try:
            # Auto-discover the best available model
            found_model_name = None
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    if 'flash' in m.name:
                        found_model_name = m.name
                        break
            
            if not found_model_name:
                 # Fallback to any generative model
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
            # Last resort fallback
            model = genai.GenerativeModel('gemini-1.5-flash')
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
    
    if model:
        try:
            full_prompt = f"{INZAGHI_SYSTEM_PROMPT}\n\nContext Information:\nCurrent Time: {current_time}\n{context_text}\n\nUser Message: {user_msg}\n\nResponse:"
            
            # Generate
            llm_response = model.generate_content(full_prompt)
            response_text = llm_response.text
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            response_text = f"Maaf ka! I'm having trouble thinking right now. (Error: {str(e)})"
    else:
        response_text = "Gemini API Key is missing! I need it to wake up."

    # 3. Save Context & History
    conversation_manager.add_message("bot", response_text)
    
    return ChatResponse(response=response_text, suggestions=candidates)
