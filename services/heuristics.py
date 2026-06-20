import re
import time
from typing import Dict, List, Optional

# In-memory storage for join timestamps to track rate limits for each chat/channel
# Format: {chat_id: [timestamp1, timestamp2, ...]}
_join_tracker: Dict[int, List[float]] = {}

# Phishing and IP logger keywords/domains to flag
IP_LOGGER_DOMAINS = [
    "grabify.link", "iplogger.org", "iplogger.com", "iplogger.ru", 
    "2no.co", "yip.su", "iplis.ru", "url0.ru", "shst.me"
]

def check_join_rate(chat_id: int, threshold_per_minute: int = 20) -> bool:
    """
    Tracks and checks if the rate of user joins in a chat exceeds the threshold.
    Returns True if join rate is abnormally high (under attack).
    """
    now = time.time()
    if chat_id not in _join_tracker:
        _join_tracker[chat_id] = []
    
    # Remove timestamps older than 60 seconds
    _join_tracker[chat_id] = [t for t in _join_tracker[chat_id] if now - t < 60]
    
    # Append current join
    _join_tracker[chat_id].append(now)
    
    # If the count exceeds the threshold, rate limit is hit
    return len(_join_tracker[chat_id]) > threshold_per_minute

def is_suspicious_profile(
    first_name: Optional[str], 
    last_name: Optional[str], 
    username: Optional[str], 
    bio: Optional[str], 
    has_photo: bool
) -> bool:
    """
    Heuristic check to determine if a joining account has bot-like features.
    Matches empty profiles, names with repeating letters (like 'TTTTT'), and missing usernames.
    """
    name_str = f"{first_name or ''} {last_name or ''}".strip()
    
    # 1. Check for repeating character patterns in the name (e.g., 'TTTTT', 'xxxxx', 'aaaa')
    # Match any letter repeating 4 or more times consecutively
    if re.search(r'([a-zA-Zа-яА-Я])\1{3,}', name_str):
        return True
    
    # 2. Check for empty profile features: no photo, no username, and no bio
    if not has_photo and not username and not bio:
        return True

    # 3. Check for typical bot name structures: gibberish random letters (e.g. constant consonants with no vowels)
    # Only run if name is long enough
    if len(name_str) >= 6:
        consonants = re.findall(r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]', name_str)
        vowels = re.findall(r'[aeiouyAEIOUY]', name_str)
        # If there are almost no vowels compared to consonants, it's gibberish (e.g., "sdfghj")
        if len(vowels) == 0 and len(consonants) >= 5:
            return True

    return False

def contains_stealth_ad_keywords(text: str) -> bool:
    """
    Quick local check for common stealth advertising triggers.
    Checks for phrases prompting users to look at profiles/bio.
    """
    text_lower = text.lower()
    patterns = [
        r"посмотри.*профил",
        r"глянь.*профил",
        r"инфа.*био",
        r"ссылка.*профил",
        r"канал.*био",
        r"в.*описани.*профил",
        r"check.*profile",
        r"link.*bio",
        r"info.*profile"
    ]
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return True
    return False

def extract_urls(text: str) -> List[str]:
    """Extract all URLs from a text message."""
    url_pattern = r'https?://[^\s]+'
    return re.findall(url_pattern, text)

def is_malicious_link(url: str) -> bool:
    """
    Checks if a URL belongs to a known IP logger domain or phishing pattern.
    """
    url_lower = url.lower()
    # Check for direct IP loggers
    for domain in IP_LOGGER_DOMAINS:
        if domain in url_lower:
            return True
    return False
