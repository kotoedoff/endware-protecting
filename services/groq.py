import base64
import json
import logging
from typing import Dict, Any, Optional
from groq import AsyncGroq
import config
from database.crud import get_chat_settings
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

def get_groq_client(api_key: Optional[str]) -> Optional[AsyncGroq]:
    """Helper to initialize AsyncGroq with a given key."""
    if not api_key:
        return None
    return AsyncGroq(api_key=api_key)

async def analyze_text(text: str, chat_id: int, db_session: AsyncSession) -> Dict[str, Any]:
    """
    Analyze text for stealth ads, spam, and illegal content using Groq with Llama 4 Scout.
    Falls back to global text key if custom key is not configured for the chat.
    """
    settings = await get_chat_settings(db_session, chat_id)
    api_key = settings.custom_groq_key_text or config.GROQ_API_KEY_TEXT
    
    client = get_groq_client(api_key)
    if not client:
        logger.warning(f"No Groq Text API Key configured for chat {chat_id}. Skipping AI analysis.")
        return {"is_violation": False, "reason": "no_api_key"}

    system_prompt = (
        "You are an AI security assistant moderating a Telegram group/channel. "
        "Analyze the message for violations. Check for:\n"
        "1. Direct spam or advertising.\n"
        "2. Stealth advertising (e.g. telling users to visit their profile or bio for links/channels, "
        "e.g., 'Look at my profile', 'Information in my bio').\n"
        "3. Illegal content (drugs promotion, selling weapons, carding, scamming).\n\n"
        "Your response MUST be a JSON object with this exact structure:\n"
        "{\n"
        "  \"is_violation\": true/false,\n"
        "  \"reason\": \"spam\" / \"stealth_ad\" / \"illegal\" / \"none\",\n"
        "  \"explanation\": \"brief explanation in Russian\"\n"
        "}\n"
        "Return ONLY the raw JSON block. Do not include markdown code block syntax (like ```json) or explanation text."
    )

    try:
        completion = await client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.1,  # Low temperature for deterministic classification
            response_format={"type": "json_object"}
        )
        
        response_text = completion.choices[0].message.content
        return json.loads(response_text)
    except Exception as e:
        logger.error(f"Error during Groq text analysis: {e}")
        return {"is_violation": False, "reason": "error", "explanation": str(e)}

async def analyze_image(image_bytes: bytes, chat_id: int, db_session: AsyncSession) -> Dict[str, Any]:
    """
    Analyze an image for NSFW or illegal content (drugs, weapons) using Llama 4 Scout Vision.
    Falls back to global vision key if custom key is not configured for the chat.
    """
    settings = await get_chat_settings(db_session, chat_id)
    api_key = settings.custom_groq_key_vision or config.GROQ_API_KEY_VISION
    
    client = get_groq_client(api_key)
    if not client:
        logger.warning(f"No Groq Vision API Key configured for chat {chat_id}. Skipping AI analysis.")
        return {"is_violation": False, "reason": "no_api_key"}

    # Encode image to base64
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    system_prompt = (
        "You are an AI security assistant moderating a Telegram group/channel. "
        "Analyze the attached image for safety violations. Check for:\n"
        "1. NSFW content (pornography, explicit nudity, extreme violence, gore).\n"
        "2. Illegal items (drugs, drug paraphernalia, weapons sale, illegal substances).\n\n"
        "Your response MUST be a JSON object with this exact structure:\n"
        "{\n"
        "  \"is_violation\": true/false,\n"
        "  \"reason\": \"nsfw\" / \"drugs\" / \"weapons\" / \"none\",\n"
        "  \"explanation\": \"brief explanation in Russian\"\n"
        "}\n"
        "Return ONLY the raw JSON block. Do not include markdown code block syntax or explanation text."
    )

    try:
        completion = await client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this image for safety violations."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        response_text = completion.choices[0].message.content
        return json.loads(response_text)
    except Exception as e:
        logger.error(f"Error during Groq vision analysis: {e}")
        return {"is_violation": False, "reason": "error", "explanation": str(e)}
