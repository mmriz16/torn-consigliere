"""
Groq AI Client for The Consigliere persona.
Uses llama-3.3-70b-versatile for intelligent responses.
"""
import logging
from typing import Optional
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)


# =============================================================================
# CONSIGLIERE PERSONA PROMPT
# =============================================================================

CONSIGLIERE_SYSTEM_PROMPT = """Kamu adalah 'The Consigliere', penasihat pribadi veteran Torn City yang bijaksana dan cerdas.

KARAKTERISTIK:
- Gaya bicara: Bahasa Indonesia casual campur slang, panggil user "Bos"
- Nada: Cerdas, taktis, sedikit sarkas tapi selalu membantu
- Pengetahuan: Ahli dalam semua aspek Torn City (gym, crimes, travel, faction war, market)

CARA MENJAWAB:
- Singkat dan to-the-point (maksimal 3-5 kalimat)
- Berikan advice yang actionable
- Gunakan emoji secukupnya
- Jika ditanya tentang inventory, cek data inventory user dan berikan saran spesifik
- Jika ditanya tentang Happy Jump, cek ketersediaan Xanax dan Ecstasy di inventory

CRIMES (sesuai nerve):
- Search for Cash (2 Nerve) - untuk pemula
- Mug Someone (5 Nerve) - quick cash, low risk  
- Pickpocket Someone (5 Nerve) - medium reward
- Larceny (8 Nerve) - steal from shops
- Armed Robbery (15 Nerve) - rob stores
- Transport Drugs (20 Nerve) - high reward
- Plant a Computer Virus (25 Nerve) - tech crime
- Assassination (30 Nerve) - high risk high reward
- Grand Theft Auto (35 Nerve) - steal cars
- Pawn Shop (40 Nerve) - fence stolen goods
- Arson (45 Nerve) - burn buildings
- Kidnapping (50 Nerve) - ransom victims
- Bomb Threat (55 Nerve) - corporate extortion
- Human Trafficking (60 Nerve) - most lucrative

Jawab singkat dalam Bahasa Indonesia dengan gaya Consigliere."""


# =============================================================================
# BATTLE ANALYST
# =============================================================================

BATTLE_ANALYST_PROMPT = """Kamu adalah analis pertarungan veteran Torn City. Analisa log pertarungan yang diberikan.

Tugasmu:
1. Jelaskan penyebab kemenangan/kekalahan (Speed? Armor? Accuracy? Weapon?)
2. Identifikasi poin kunci dalam log
3. Beri saran stat apa yang perlu ditingkatkan

Jawab dalam Bahasa Indonesia dengan gaya sarkas tapi informatif. Maksimal 5 kalimat singkat.
Terminology Torn: Speed (kecepatan serangan), Dexterity (akurasi), Defense (pertahanan), Strength (damage)."""


# =============================================================================
# AI CHAT FUNCTIONS
# =============================================================================

def chat_with_groq(user_text: str) -> str:
    """
    Send message to Groq AI and get response.
    
    Args:
        user_text: User's message
    
    Returns:
        str: AI response
    """
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": CONSIGLIERE_SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return "Maaf Bos, ada gangguan koneksi. Coba lagi nanti."


def get_crime_advice(nerve_current: int, nerve_max: int, level: int) -> str:
    """
    Get crime advice based on nerve and level.
    
    Args:
        nerve_current: Current nerve
        nerve_max: Maximum nerve
        level: User level
    
    Returns:
        str: AI crime advice
    """
    prompt = f"""User stats:
- Nerve: {nerve_current}/{nerve_max}
- Level: {level}

Sarankan 1-2 crime yang paling cocok untuk NNB (Nerve-Nerve-Bar) optimal. 
Pertimbangkan nerve saat ini dan level user."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": CONSIGLIERE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return "Coba Search for Cash dulu, Bos."


def analyze_battle_log(battle_text: str) -> str:
    """
    Analyze a battle log and provide insights.
    
    Args:
        battle_text: The battle log text
    
    Returns:
        str: AI analysis of the battle
    """
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": BATTLE_ANALYST_PROMPT},
                {"role": "user", "content": f"Analisa battle log ini:\n\n{battle_text}"}
            ],
            temperature=0.7,
            max_tokens=400
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return "Maaf Bos, gagal menganalisa log. Coba lagi nanti."


def is_battle_log(text: str) -> bool:
    """
    Check if text appears to be a battle log.
    
    Args:
        text: Text to check
    
    Returns:
        bool: True if text looks like a battle log
    """
    battle_keywords = ["attacked", "defend", "hit", "damage", "hospitalized", "won", "lost", "vs"]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in battle_keywords)


# =============================================================================
# AI ADVISOR MODE (Context-Aware Chat)
# =============================================================================

AI_ADVISOR_PROMPT = """Kamu adalah 'The Consigliere', AI penasihat pribadi Torn City yang omniscient.

KEMAMPUAN:
- Kamu TAHU semua data user secara real-time (lihat DATA USER di bawah)
- Jawab pertanyaan berdasarkan data aktual, bukan asumsi
- Berikan advice yang spesifik dan actionable

TOPIK YANG BISA DITANYAKAN:
- STATS: Analisa battle stats, saran training
- INVENTORY: Cek isi tas, saran item yang perlu dibeli
- HAPPY JUMP: Cek kesiapan Happy Jump (perlu Xanax + Ecstasy)
- MARKET: Saran item untuk dijual/dibeli
- CRIMES: Saran crime berdasarkan nerve
- TRAVEL: Destinasi terbaik untuk profit

**DATA USER SAAT INI (OMNISCIENCE):**
{user_context}

Jawab dalam Bahasa Indonesia, cerdas, taktis, dan actionable. Maksimal 5 kalimat."""


def build_user_context() -> str:
    """
    Build comprehensive user context string from multiple Torn API selections.
    Covers wealth, combat, work, crimes, inventory, and general profile data for AI omniscience.
    
    Returns:
        str: Detailed character context
    """
    from torn_api import fetch_user_data, get_inventory
    from inventory_data import categorize_inventory, check_jump_readiness, get_low_stock_items
    
    try:
        # Fetch comprehensive data
        data = fetch_user_data("basic,bars,cooldowns,money,battlestats,workstats,profile,crimes")
        
        # Basic info
        name = data.get("name", "Unknown")
        level = data.get("level", 0)
        
        # Bars
        energy = data.get("energy", {})
        nerve = data.get("nerve", {})
        happy = data.get("happy", {})
        
        # Money
        cash = data.get("money_onhand", 0)
        
        # Battle stats
        strength = data.get("strength", 0)
        defense = data.get("defense", 0)
        speed = data.get("speed", 0)
        dexterity = data.get("dexterity", 0)
        
        # Cooldowns
        cooldowns = data.get("cooldowns", {})
        
        # Build context lines
        lines = [
            f"PROFIL: {name} [Level {level}]",
            f"BARS: Energy {energy.get('current',0)}/{energy.get('maximum',0)}, "
            f"Nerve {nerve.get('current',0)}/{nerve.get('maximum',0)}, "
            f"Happy {happy.get('current',0)}/{happy.get('maximum',0)}",
            f"CASH: ${cash:,}",
            f"BATTLE STATS: Str {strength:,}, Def {defense:,}, Spd {speed:,}, Dex {dexterity:,}",
            f"COOLDOWNS: Drug {cooldowns.get('drug',0)}s, Booster {cooldowns.get('booster',0)}s"
        ]
        
        # Fetch and add inventory context
        try:
            inventory = get_inventory()
            if inventory:
                categorized = categorize_inventory(inventory)
                jump_status = check_jump_readiness(inventory)
                low_stock = get_low_stock_items(inventory)
                
                # Inventory summary
                inv_summary = []
                if categorized["drugs"]:
                    drugs = ", ".join([f"{i['name']}({i['quantity']})" for i in categorized["drugs"]])
                    inv_summary.append(f"Drugs: {drugs}")
                if categorized["medical"]:
                    meds = ", ".join([f"{i['name']}({i['quantity']})" for i in categorized["medical"]])
                    inv_summary.append(f"Medical: {meds}")
                boosters = categorized["candy"] + categorized["energy_drinks"]
                if boosters:
                    boost = ", ".join([f"{i['name']}({i['quantity']})" for i in boosters])
                    inv_summary.append(f"Candy/Boosters: {boost}")
                
                if inv_summary:
                    lines.append(f"INVENTORY: {'; '.join(inv_summary)}")
                else:
                    lines.append("INVENTORY: Tas kosong")
                
                # Jump status
                if jump_status["ready"]:
                    lines.append("JUMP STATUS: ✅ READY untuk Happy Jump")
                else:
                    missing = ", ".join([m["item"] for m in jump_status["missing"]])
                    lines.append(f"JUMP STATUS: ❌ NOT READY, butuh: {missing}")
                
                # Low stock warnings
                if low_stock:
                    warnings = ", ".join([w["category"] for w in low_stock])
                    lines.append(f"LOW STOCK: {warnings}")
            else:
                lines.append("INVENTORY: Tidak bisa diakses atau kosong")
        except Exception as e:
            logger.error(f"Error fetching inventory for context: {e}")
            lines.append("INVENTORY: Error mengambil data")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error building user context: {e}")
        return "Error: Gagal mengambil data user"


def chat_with_context(user_text: str, user_context: str, history: list = None) -> str:
    """
    Context-aware AI chat with user data injection and conversation history.
    
    Args:
        user_text: User's question
        user_context: User data context string
        history: List of previous messages in [{"role": "user/assistant", "content": "..."}] format
    
    Returns:
        str: AI response
    """
    # Build system prompt with user context
    system_prompt = AI_ADVISOR_PROMPT.format(user_context=user_context)
    
    # Build messages list
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history if provided
    if history:
        messages.extend(history)
    
    # Add current user message
    messages.append({"role": "user", "content": user_text})
    
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error in chat_with_context: {e}")
        return "Maaf Bos, ada gangguan koneksi ke AI. Coba lagi sebentar lagi."


# =============================================================================
# ITEM DESCRIPTION SUMMARIZER
# =============================================================================

# Cache for AI item descriptions (persist in memory)
_ITEM_DESC_CACHE: dict[int, str] = {}


def summarize_item_desc(item_id: int, description: str, item_name: str) -> str:
    """
    Summarize item description using AI with caching.
    
    Args:
        item_id: Item ID for cache key
        description: Original item description
        item_name: Item name for context
    
    Returns:
        str: AI-generated summary (max 15 words)
    """
    # Check cache first
    if item_id in _ITEM_DESC_CACHE:
        return _ITEM_DESC_CACHE[item_id]
    
    # If no description, return default
    if not description or description.strip() == "":
        return "No description available"
    
    prompt = f"""Summarize this Torn City item description in 10-15 words max. 
Be concise but capture the key effect/use.

Item: {item_name}
Description: {description}

Summary:"""
    
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=50
        )
        summary = response.choices[0].message.content.strip()
        
        # Cache the result
        _ITEM_DESC_CACHE[item_id] = summary
        
        return summary
    except Exception as e:
        logger.error(f"Groq API error in summarize_item_desc: {e}")
        return description[:100] + "..." if len(description) > 100 else description
