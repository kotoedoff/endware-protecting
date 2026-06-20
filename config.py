import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Bot Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN must be specified in the environment or .env file")

# Groq API Keys (Fallback defaults)
GROQ_API_KEY_TEXT = os.getenv("GROQ_API_KEY_TEXT")
GROQ_API_KEY_VISION = os.getenv("GROQ_API_KEY_VISION")

# Model configuration
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# Global Hoster/Owner ID
try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
except ValueError:
    OWNER_ID = 0

# Database path
DATABASE_PATH = BASE_DIR / "endware_bot.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"
