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

@app.on_event("startup")
def startup_event():
    global manager
    
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
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            logger.info("Gemini SDK Configured.")
        except Exception as e:
            logger.error(f"Error configuring Gemini SDK: {e}")
    else:
        logger.warning("GEMINI_API_KEY not found. Please set it in .env")

# ... (Search endpoints helper classes unchanged) ...

# ... (Helper function get_relevant_candidates unchanged) ...

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

    # 2. Generate Response
    response_text = ""
    
    if GEMINI_API_KEY:
        try:
            full_prompt = f"{INZAGHI_SYSTEM_PROMPT}\n\nContext Information:\nCurrent Time: {current_time}\n{context_text}\n\nUser Message: {user_msg}\n\nResponse:"
            
            # List of models to try
            models_to_try = [
                "gemini-1.5-flash",
                "gemini-1.5-flash-latest",
                "gemini-pro",
                "gemini-1.0-pro"
            ]
            
            last_error = None
            import time
            
            for model_name in models_to_try:
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
