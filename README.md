# 🍔 Inzaghi - Peshawar Foodie AI

<div align="center">
  <img src="frontend/src/assets/logo_transparent.png" alt="Inzaghi Logo" width="200" />
  
  <h3>Your Friendly AI Companion for Finding the Best Food in Peshawar!</h3>

  <p>
    <b>Inzaghi</b> is an intelligent, context-aware chatbot designed to help food lovers navigate the culinary landscape of Peshawar. Matches your budget, location, and cravings with the perfect restaurant.
  </p>
</div>

---

## 📖 Project Overview

**Inzaghi** is not just a search engine; it's a **Persona-based AI Assistant** that understands the local context. Built with a modern tech stack, it combines structured data searching (budget, location, menu) with the generative capabilities of **Google Gemini LLM** to provide natural, conversational responses.

### 🌟 Key Features

*   **🧠 Context-Aware AI**: Powered by **Google Gemini**, Inzaghi understands natural language queries like *"I want spicy food near University Road under 500"*
*   **🎭 Unique Persona**: A friendly, local "Peshawari" personality that makes interactions fun and engaging.
*   **💰 Smart Budget Filtering**: Automatically extracts price limits from your messages to commend affordable options.
*   **📍 Location Intelligence**: Filters restaurants based on local areas (e.g., University Road, Hayatabad).
*   **🎨 Premium UI/UX**: A stunning "Glassmorphism" interface built with **React** & **Tailwind CSS**, featuring dark mode, smooth animations, and a "Thinking" state.
*   **⚡ Real-time Suggestions**: Displays structured restaurant cards (Rating, Price, Deals) alongside the AI chat response.

---

## 🛠️ Technology Stack

### **Frontend (Client-Side)**
*   **React (Vite)**: Fast, modern UI library.
*   **Tailwind CSS**: Utility-first styling for the custom "Dark Glass" aesthetic.
*   **Lucide React**: Beautiful, consistent iconography.
*   **Framer Motion / CSS Animations**: For smooth transitions and the "Thinking" pulse effect.

### **Backend (Server-Side)**
*   **FastAPI (Python)**: High-performance web API framework.
*   **Google Gemini API**: state-of-the-art Large Language Model for reasoning and chat generation.
*   **RAG (Retrieval-Augmented Generation)**: Custom heuristic engine helps select the best restaurant data to feed the AI context.
*   **Docker**: Containerization for consistent deployment.

---

## 🚀 How It Works (Architecture)

1.  **User Query**: You send a message (e.g., *"Suggestion for pizza?"*).
2.  **Analysis (Backend)**:
    *   The server extracts **Keywords** (Location, Food Item, Budget regex).
    *   It queries the **Local Database** (`restaurants_data.json`) for matches.
3.  **Context Construction**:
    *   Top relevant restaurant matches (filtering by budget/location) are converted into text context.
    *   The **System Prompt** ("You are Inzaghi...") teaches the AI how to behave.
4.  **Generative AI**:
    *   The User Query + Context + System Prompt are sent to **Gemini**.
    *   Gemini generates a friendly response using the data provided.
5.  **Response**: The frontend displays the text and renders interactive **Suggestion Cards**.

---

## 💻 Installation & Setup

Follow these steps to run the project locally.

### Prerequisites
*   Node.js (for frontend)
*   Python 3.8+ (for backend)
*   A Google Gemini API Key

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment (optional but recommended)
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure Environment
# Create a .env file in /backend and add:
# GEMINI_API_KEY=your_api_key_here

# Run Server
uvicorn main:app --reload
# Server starts at http://localhost:8000
```

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run Development Server
npm run dev
# App starts at http://localhost:5173
```

---

## 🐳 Docker Deployment

To build and run the entire stack using Docker:

```bash
# Build the image
docker build -t inzaghi-bot .

# Run the container
docker run -p 8000:8000 inzaghi-bot
```

---

## 🔮 Future Roadmap

*   [ ] **Voice Interface**: Talk to Inzaghi directly.
*   [ ] **User Accounts**: Save your favorite spots.
*   [ ] **Live Maps Integration**: Show restaurants on a map.
*   [ ] **Urdu/Pashto Support**: Local language localization.

---

<div align="center">
  <p>Made with ❤️ in Peshawar</p>
</div>
