# 🎩 The Consigliere v4.0

**Personal Telegram Bot untuk Torn City** - Bot asisten pribadi dengan fitur AI advisor, real-time monitoring, dan multi-menu dashboard.

> Bot ini dirancang untuk personal use dengan autentikasi USER_ID.

---

## 🌟 Fitur Utama

### 📊 Multi-Menu Dashboard (V2.0)
Dashboard real-time dengan navigasi emoji yang compact dan intuitif:

| Emoji | Menu | Deskripsi |
|:---:|---|---|
| 📊 | **Stats Hub** | **NEW!** Status summary + Inline: 📩 Inbox, 🔔 Events, 🏅 Awards |
| 🏠 | **Property** | Info properti, happy bonus, property market browser |
| 🏋️ | **Gym** | Battle stats, predictive gains, gym info |
| 💼 | **Job** | Company info, job points, work stats |
| 🛡️ | **Gear** | Equipped weapons & armor dengan stats detail |
| 🔫 | **Criminal** | Criminal record dengan XP tracker untuk leveling |
| 💰 | **Market** | Item search dengan harga bazaar & market |
| 💬 | **AI Advisor** | Context-aware AI chat (Groq llama-3.3-70b) |
| ✈️ | **Travel** | Status perjalanan dan info negara |

### 🧠 AI-Powered Features
- **AI Crime Advisor** - Saran crime berdasarkan nerve dan level
- **Battle Log Analysis** - Analisa pertarungan dengan saran improvement
- **AI Advisor Chat** - Context-aware assistant dengan data karakter real-time
- **Item Description Summarizer** - AI summary untuk item descriptions

### ⏰ Background Monitoring (Scheduler)
Notifikasi otomatis yang berjalan di background:

| Alert | Trigger |
|---|---|
| 🔋 Energy Full | Energy bar penuh |
| 💢 Nerve Full | Nerve bar penuh |
| 🏥 Hospital Exit | Keluar dari rumah sakit |
| 💊 Drug Cooldown | Cooldown drug selesai |
| 💉 Booster Cooldown | Cooldown booster selesai |
| ✈️ Travel Landing | 2 menit sebelum landing |
| 📚 Education | 1 jam sebelum course selesai |
| 📢 Event Watcher | New events (Satpam System) |

### 🏠 Property Market Browser
- Browse rental & selling listings per property type
- Holy Trinity filter (Airstrip + Vault + Medical Lab)
- Best Value algorithm dengan cost-to-happiness ratio
- Budget warning indicator

### 🎯 Baldr's Leveling Targets
- Database target untuk training (dari `baldr_targets.json`)
- Filter by level range
- Refresh callback untuk update data

---

## 📁 Struktur Proyek

```
bot-torn/
├── main.py              # Entry point, Flask keep-alive, handlers registration
├── handlers.py          # Telegram command & message handlers (2700+ lines)
├── torn_api.py          # Torn API client dengan endpoint wrapper
├── scheduler.py         # APScheduler untuk background monitoring
├── groq_client.py       # Groq AI client (llama-3.3-70b-versatile)
├── config.py            # Environment variables loader
├── property_data.py     # Property types & market helpers
├── travel_data.py       # Country data & travel items untuk smuggling
├── item_cache.py        # Item database caching
├── items.py             # Item utilities
├── utils.py             # Utility functions
├── baldr_targets.json   # Static leveling target database
├── state.json           # Persistent state storage
├── requirements.txt     # Python dependencies
└── .env                 # Environment variables (git-ignored)
```

---

## ⚙️ Instalasi

### 1. Clone Repository
```bash
git clone <repository-url>
cd bot-torn
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Environment Variables
Buat file `.env` dengan isi:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
USER_ID=your_telegram_user_id
TORN_API_KEY=your_torn_full_access_api_key
GROQ_API_KEY=your_groq_api_key
```

| Variable | Deskripsi |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token dari [@BotFather](https://t.me/BotFather) |
| `USER_ID` | Telegram user ID Anda (untuk autentikasi) |
| `TORN_API_KEY` | Torn API key dengan **Full Access** |
| `GROQ_API_KEY` | API key dari [console.groq.com](https://console.groq.com) |

### 4. Jalankan Bot
```bash
python main.py
```

Bot akan berjalan dengan:
- HTTP server di port 8080 (untuk keep-alive)
- Telegram polling untuk menerima pesan
- Background scheduler untuk monitoring

---

## 📋 Dependencies

| Package | Version | Fungsi |
|---|:---:|---|
| `python-telegram-bot` | ≥20.0 | Telegram Bot API |
| `groq` | ≥0.4.0 | Groq AI client |
| `requests` | ≥2.28.0 | HTTP requests ke Torn API |
| `apscheduler` | ≥3.10.0 | Background job scheduler |
| `python-dotenv` | ≥1.0.0 | Environment variable loader |
| `flask` | latest | HTTP server untuk keep-alive |

---

## 🔧 Commands

| Command | Deskripsi |
|---|---|
| `/start` | Tampilkan dashboard dengan reply keyboard menu |
| `/help` | Panduan penggunaan bot |

> **Note:** Semua fitur utama diakses melalui **Reply Keyboard** emoji buttons, bukan commands.

---

## 🛠️ Teknologi

- **Python 3.10+**
- **python-telegram-bot** v20+ (async/await)
- **Groq API** dengan model `llama-3.3-70b-versatile`
- **APScheduler** untuk async background jobs
- **Flask** untuk HTTP keep-alive endpoint
- **Torn API v1 & v2**

---

## 🔐 Security

- Bot menggunakan **autentikasi USER_ID** - hanya user dengan ID yang terdaftar di `.env` yang dapat mengakses bot
- API keys disimpan di environment variables (tidak di-commit ke git)
- Rate limiting dihandle oleh Torn API

---

## 📝 License

Personal use only. Not affiliated with Torn City.

---

## 🤝 Credits

- **Torn City** - [torn.com](https://www.torn.com)
- **Groq** - [groq.com](https://groq.com) untuk AI model
- **Baldr** - Leveling targets database
