from dotenv import load_dotenv
load_dotenv()  # Must be first

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pathlib import Path
import os
import logging

from routes import chat_routes

# # --- Load environment variables ---
# load_dotenv()

# --- Configure logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Ensure Gemini API key is available for backend ---
# If GEMINI_API_KEY not set, copy from VITE_GEMINI_API_KEY
if not os.getenv("GEMINI_API_KEY") and os.getenv("VITE_GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.getenv("VITE_GEMINI_API_KEY")

# Log keys presence (no actual values for safety)
logging.info(f"MURF_API_KEY loaded: {bool(os.getenv('MURF_API_KEY'))}")
logging.info(f"ASSEMBLYAI_API_KEY loaded: {bool(os.getenv('ASSEMBLYAI_API_KEY'))}")
logging.info(f"GEMINI_API_KEY loaded: {bool(os.getenv('GEMINI_API_KEY'))}")

# --- Create uploads dir ---
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# --- Init FastAPI ---
app = FastAPI()

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routes ---
app.include_router(chat_routes.router)

# --- Serve uploads ---
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
