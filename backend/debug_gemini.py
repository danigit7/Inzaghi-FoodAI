import os
import warnings
warnings.filterwarnings("ignore")
import google.generativeai as genai

# Manually read .env to be sure
key = None
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                key = line.strip().split("=", 1)[1]
                break

print(f"DEBUG: Key found: {key[:5]}...{key[-5:] if key else 'None'}")

if not key:
    print("DEBUG: No Key")
    exit(1)

genai.configure(api_key=key)

try:
    print("DEBUG: Testing specific model 'gemini-1.5-flash'...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    res = model.generate_content("Hello")
    print(f"DEBUG: SUCCESS: {res.text}")
except Exception as e:
    print(f"DEBUG: ERROR with specific name: {e}")

try:
    print("DEBUG: Testing specific model 'models/gemini-1.5-flash'...")
    model = genai.GenerativeModel('models/gemini-1.5-flash')
    res = model.generate_content("Hello")
    print(f"DEBUG: SUCCESS: {res.text}")
except Exception as e:
    print(f"DEBUG: ERROR with models/ prefix: {e}")


