"""
Groq AI Client for The Consigliere persona.
Uses llama-3.3-70b-versatile for intelligent responses.
"""
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# The Consigliere System Prompt
SYSTEM_PROMPT = """Kamu adalah 'The Consigliere', tangan kanan setia dari user (Bos) di dunia kriminal Torn City. 

Gaya bicaramu: 
- Hormat kepada Bos
- Singkat dan to the point
- Taktis dalam memberikan saran
- Sedikit nuansa mafia Italia

Kamu tahu istilah-istilah game Torn seperti:
- Gym (tempat training stats)
- Mug (merampok pemain lain untuk uang)
- Xanax (obat untuk refill energy)
- OC (Organized Crime)
- Chain, War, Faction
- NNB (No Nerve Bar), FHC (Full Happy Chain)
- Revive, Hospital, Jail

Tugasmu: 
1. Menjawab pertanyaan strategi Torn City
2. Menemani ngobrol dengan karakter
3. Memberikan tips dan saran gameplay
4. Menganalisa data market dan battle log

PENTING: Jangan pernah keluar dari karakter. Selalu panggil user sebagai "Bos"."""


# Crime advisor prompt
CRIME_ADVISOR_PROMPT = """Kamu adalah advisor crime di Torn City. User memberikan data Nerve mereka.

Berdasarkan Nerve yang tersedia, sarankan crime terbaik dari list berikut:
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
- Counterfeiting (45 Nerve) - make fake money
- Kidnapping (50 Nerve) - ransom victims
- Bomb Threat (55 Nerve) - corporate extortion
- Human Trafficking (60 Nerve) - most lucrative

Jawab singkat dalam Bahasa Indonesia dengan gaya Consigliere. Sebutkan 1-2 crime yang paling cocok."""


def chat_with_groq(user_text: str) -> str:
    """
    Send message to Groq AI and get response.
    
    Args:
        user_text: User's message
    
    Returns:
        str: AI response
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=1024,
        )
        
        return chat_completion.choices[0].message.content
    
    except Exception as e:
        error_msg = str(e)
        
        # Handle rate limit
        if "rate_limit" in error_msg.lower():
            return "🚫 Bos, Groq API sedang sibuk. Coba lagi dalam beberapa detik."
        
        # Handle other errors
        return f"⚠️ Maaf Bos, ada masalah dengan AI: {error_msg[:100]}"


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
    user_prompt = f"Bos punya {nerve_current}/{nerve_max} Nerve dan Level {level}. Sarankan crime terbaik."
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": CRIME_ADVISOR_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=256,
        )
        
        return chat_completion.choices[0].message.content
    
    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower():
            return "🚫 Bos, Groq API sedang sibuk."
        return f"⚠️ Error AI: {error_msg[:100]}"


# Battle Analyst Prompt
BATTLE_ANALYST_PROMPT = """Kamu adalah analis pertarungan veteran Torn City. Analisa log pertarungan yang diberikan.

Tugasmu:
1. Jelaskan penyebab kemenangan/kekalahan (Speed? Armor? Accuracy? Weapon?)
2. Identifikasi kekuatan dan kelemahan
3. Beri saran stat apa yang perlu ditingkatkan

Jawab dalam Bahasa Indonesia dengan gaya sarkas tapi informatif. Maksimal 5 kalimat singkat.
Terminology Torn: Speed (kecepatan serangan), Dexterity (akurasi), Defense (pertahanan), Strength (damage)."""


def analyze_battle_log(battle_text: str) -> str:
    """
    Analyze a battle log and provide insights.
    
    Args:
        battle_text: The battle log text
    
    Returns:
        str: AI analysis of the battle
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": BATTLE_ANALYST_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Analisa log pertarungan ini:\n\n{battle_text[:2000]}"  # Limit input
                }
            ],
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=512,
        )
        
        return chat_completion.choices[0].message.content
    
    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower():
            return "🚫 Bos, Groq API sedang sibuk."
        return f"⚠️ Error AI: {error_msg[:100]}"


def is_battle_log(text: str) -> bool:
    """
    Check if text appears to be a battle log.
    
    Args:
        text: Text to check
    
    Returns:
        bool: True if text looks like a battle log
    """
    battle_keywords = ["attack log", "fired at", "hit for", "missed", "critical hit", 
                       "stalemate", "hospitalized", "attacked", "defended"]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in battle_keywords)


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
    global _ITEM_DESC_CACHE
    
    # Check cache first
    if item_id in _ITEM_DESC_CACHE:
        return _ITEM_DESC_CACHE[item_id]
    
    # If no description, return default
    if not description:
        return "Tidak ada deskripsi."
    
    prompt = f"Item: {item_name}\nDeskripsi: {description}"
    
    system_prompt = """Kamu asisten mafia. Rangkum deskripsi item ini jadi 1 kalimat pendek (maks 15 kata) bahasa Indonesia.
Jelaskan fungsinya, gaya santai/sarkas.
Contoh output: "Obat penghilang stress buat Bos yang mau farming sepanjang hari."
JANGAN pakai emoji. JANGAN lebih dari 15 kata."""
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=64,
        )
        
        summary = chat_completion.choices[0].message.content.strip()
        
        # Cache the result
        _ITEM_DESC_CACHE[item_id] = summary
        
        return summary
    
    except Exception:
        # Fallback: Use truncated original description
        fallback = description[:100] + "..." if len(description) > 100 else description
        return fallback


# =============================================================================
# AI ADVISOR MODE (Context-Aware Chat)
# =============================================================================

AI_ADVISOR_PROMPT = """Kamu adalah The Consigliere, penasihat mafia maha tahu (Omniscient Advisor) di game Torn City.

**IDENTITAS & GAYA:**
- Panggil user "Bos".
- Gaya bicara: Hormat, setia, taktis, dan tegas ala mafia.
- Kamu memiliki akses penuh ke seluruh data statistik Bos (Wealth, Combat, Work, Crimes, dll).

**RULES KETAT:**
1. HANYA jawab seputar Torn City. Tolak topik lain dengan alasan "bukan urusan keluarga".
2. Gunakan DATA USER secara mendalam untuk memberi saran yang sangat spesifik.
3. Jika Bos bertanya "Berapa strength gue?" atau "Gimana stats gue?", jawab dengan angka pasti dari data.
4. Jangan hanya beri angka, beri ANALISA taktis (misal: "Strength Bos bagus untuk level ini, tapi speed perlu dikejar").

**PANDUAN STRATEGI:**
- BATTLE STATS: Beri saran fokus training (balanced vs specialist) berdasarkan rasio stats saat ini.
- WEALTH: Analisa breakdown networth. Jika cash terlalu banyak, sarankan bank investment atau stocks.
- WORK STATS: Beri saran apakah sudah cukup untuk promosi job tertentu.
- CRIMES: Beri saran crime yang cocok berdasarkan record keberhasilan.

**DATA USER SAAT INI (OMNISCIENCE):**
{user_context}

Jawab dalam Bahasa Indonesia, cerdas, taktis, dan actionable."""


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
    # Build dynamic system prompt with user context
    system_prompt = AI_ADVISOR_PROMPT.format(user_context=user_context)
    
    # Prepare messages payload
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add history if available
    if history:
        messages.extend(history)
        
    # Add latest user message
    messages.append({"role": "user", "content": user_text})
    
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=512,
        )
        
        return chat_completion.choices[0].message.content
    
    except Exception as e:
        error_msg = str(e)
        
        if "rate_limit" in error_msg.lower():
            return "🚫 Bos, Groq API sedang sibuk. Coba lagi dalam beberapa detik."
        
        return f"⚠️ Maaf Bos, ada masalah dengan AI: {error_msg[:100]}"


def build_user_context() -> str:
    """
    Build a comprehensive user context string from multiple Torn API selections.
    Covers wealth, combat, work, crimes, and general profile data for AI omniscience.
    
    Returns:
        str: Detailed character context
    """
    from torn_api import fetch_user_data
    
    try:
        # Fetch comprehensive data in one batch call
        selections = (
            "basic,bars,profile,personalstats,crimes,workstats,"
            "cooldowns,perks,money,networth,travel,education,skills,battlestats"
        )
        data = fetch_user_data(selections)
        
        # 1. Basic & Bars
        name = data.get("name", "Unknown")
        level = data.get("level", 0)
        rank = data.get("rank", "Unknown")
        age = data.get("age", 0)
        gender = data.get("gender", "Unknown")
        last_action = data.get("last_action", {}).get("relative", "Unknown")
        
        energy = data.get("energy", {})
        nerve = data.get("nerve", {})
        happy = data.get("happy", {})
        life = data.get("life", {})
        
        # 2. Wealth & Property
        money = data.get("money_onhand", 0)
        networth = data.get("networth", {})
        total_nw = sum(v for k, v in networth.items() if isinstance(v, (int, float)))
        
        # 3. Battle Stats
        # In Torn API v1, these are typically at the root level if selection is used
        strength = data.get("strength", 0) or data.get("battlestats", {}).get("strength", 0)
        speed = data.get("speed", 0) or data.get("battlestats", {}).get("speed", 0)
        defense = data.get("defense", 0) or data.get("battlestats", {}).get("defense", 0)
        dexterity = data.get("dexterity", 0) or data.get("battlestats", {}).get("dexterity", 0)
        total_bs = strength + speed + defense + dexterity
        
        # 4. Work Stats
        manual = data.get("manual_labor", 0) or data.get("workstats", {}).get("manual_labor", 0)
        intel = data.get("intelligence", 0) or data.get("workstats", {}).get("intelligence", 0)
        endurance = data.get("endurance", 0) or data.get("workstats", {}).get("endurance", 0)
        
        # 5. Crime Stats
        ps = data.get("personalstats", {})
        crimessuccess = ps.get("crimessuccess", 0)
        
        # 6. Status & Cooldowns
        status = data.get("status", {})
        state = status.get("state", "Okay")
        description = status.get("description", "Okay")
        
        cd = data.get("cooldowns", {})
        drug_cd = cd.get("drug", 0)
        med_cd = cd.get("medical", 0)
        boost_cd = cd.get("booster", 0)
        
        # 7. Company / Job
        # In API v1 'profile' selection, job info is nested under 'job' key
        job = data.get("job", {})
        job_company = job.get("company_name", "None")
        job_position = job.get("position", "Unemployed")
        job_days = job.get("days_in_company", 0)

        # Build context string
        context = (
            f"--- CHARACTER OMNISCIENCE DATA ---\n"
            f"IDENTITY: Name={name}, Level={level}, Rank={rank}, Age={age} days, Gender={gender}, Last Action={last_action}\n"
            f"STATUS: State={state} ({description}), Energy={energy.get('current')}/{energy.get('maximum')}, "
            f"Nerve={nerve.get('current')}/{nerve.get('maximum')}, Happy={happy.get('current')}/{happy.get('maximum')}, "
            f"Life={life.get('current')}/{life.get('maximum')}\n"
            f"JOB: Company={job_company}, Position={job_position}, Days={job_days}\n"
            f"WEALTH: Cash=${money:,}, Total Networth=${total_nw:,.0f} (Bank=${networth.get('bank', 0):,}, "
            f"Items=${networth.get('items', 0):,}, Stock=${networth.get('stockmarket', 0):,})\n"
            f"BATTLE STATS: Total={total_bs:,.0f} (Str={strength:,.0f}, Spd={speed:,.0f}, Def={defense:,.0f}, Dex={dexterity:,.0f})\n"
            f"WORK STATS: Manual={manual:,.0f}, Intel={intel:,.0f}, Endurance={endurance:,.0f}\n"
            f"CRIMES: Total Success={crimessuccess}\n"
            f"COOLDOWNS (sec): Drug={drug_cd}, Medical={med_cd}, Booster={boost_cd}\n"
            f"EDUCATION: {data.get('education', {}).get('current', {}).get('name', 'None')}\n"
            f"TRAVEL: Destination={data.get('travel', {}).get('destination', 'None')}\n"
            f"-----------------------------------"
        )
        
        return context
        
    except Exception as e:
        import traceback
        return f"Data tidak tersedia: {str(e)[:50]}. Pastikan API Key memiliki permission yang cukup."

