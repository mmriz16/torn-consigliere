# 🎩 The Consigliere v4.2

**Personal Telegram Bot untuk Torn City** - Bot asisten pribadi dengan fitur AI advisor, real-time monitoring, Criminal Path Advisor, dan Travel Intelligence.

> Bot ini dirancang untuk personal use dengan autentikasi USER_ID.

---

## 🌟 Fitur Utama

### 📊 Multi-Menu Dashboard (V2.0)
Dashboard real-time dengan navigasi emoji yang compact dan intuitif:

| Emoji | Menu | Deskripsi |
|:---:|---|---|
| 📊 | **Stats Hub** | Status summary + Inline: 📩 Inbox, 🔔 Events, 🏅 Awards |
| 🏠 | **Property** | Info properti, happy bonus, property market browser |
| 🏋️ | **Gym** | Battle stats, predictive gains, gym info |
| 💼 | **Job** | Company info, job points, work stats |
| 🛡️ | **Gear** | Equipped weapons & armor dengan stats detail |
| 🔫 | **Criminal** | **Criminal Path Advisor** dengan EA calculator |
| 💰 | **Market** | Item search dengan harga bazaar & market |
| 💬 | **AI Advisor** | Context-aware AI chat (Groq llama-3.3-70b) |
| ✈️ | **Travel** | **Travel Intelligence** dengan profit calculator |

### 🎯 Criminal Path Advisor (NEW!)
Sistem panduan kejahatan berbasis Effective Arsons (EA):

- **EA Calculator** - Kalkulasi EA dari criminal record
- **EA Levels** - Novice → Amateur → Professional → Expert → Elite → Master → Legend
- **Crime Safety Status** - Indikator keamanan per jenis crime (🟢 Safe / 🟡 Caution / 🔴 Danger)
- **Progress Bar** - Visual progress menuju milestone berikutnya
- **Consigliere Tips** - Saran dinamis berdasarkan level EA

### ✈️ Travel Intelligence (NEW!)
Fitur kalkulasi profit travel dengan Anti-Zonk protection:

- **Top 3 Destinations** - Ranked by profit tertinggi
- **Modal Tunai** - Kalkulasi modal (Buy Price × Capacity)
- **Anti-Zonk Warning** - ⚠️ DANA KURANG! jika cash kurang
- **Profit After Tax** - Sudah termasuk pajak market 5%
- **Flight Time** - Format jam:menit (PP = Pulang-Pergi)
- **Gatekeeper Level 15** - Blokir travel untuk level < 15

### 🎯 Baldr's Leveling Targets (Enhanced!)
- 6 targets dengan level tertinggi
- Filter status "Okay" only (bukan Hospital/Jail)
- Layout compact 3-3-1
- Inline attack buttons dengan Lvl indicator

### 🧠 AI-Powered Features
- **AI Crime Advisor** - Saran crime berdasarkan nerve dan level
- **Battle Log Analysis** - Analisa pertarungan dengan saran improvement
- **AI Advisor Chat** - Context-aware assistant dengan data karakter real-time

### ⏰ Background Monitoring (Scheduler)
Notifikasi otomatis yang berjalan di background:

| Alert | Trigger |
|---|---|
| ⚡ Energy Full | Energy bar penuh |
| 🔥 Nerve Full | Nerve bar penuh |
| 🏥 Hospital Exit | Keluar dari rumah sakit |
| 💊 Drug Cooldown | Cooldown drug selesai |
| 💉 Booster Cooldown | Cooldown booster selesai |
| ✈️ **Departure Alert** | Saat mulai terbang (Pre-Flight Checklist) |
| 🛬 **Landing Alert** | 2 menit sebelum landing (Post-Landing Checklist) |
| 📚 Education | 1 jam sebelum course selesai |
| 📢 Event Watcher | New events (Satpam System) |
| 📩 Inbox Spy | Pesan baru dari player lain |

#### Departure Alert (NEW!)
```
✈️ OPERASI LINTAS NEGARA: UAE
━━━━━━━━━━━━━━━━━
📋 Pre-Flight Checklist:
• Nerve: 5/18 ✅
• Energy: 10/100 ❌ Belum habis!
• Cash: $21,099 (Modal: $112,000) ⚠️ DANA KURANG!

📦 Target: 8× Camel Plushie
💰 Est. Profit: $480,800
⏱️ ETA Landing: 4h 31m
━━━━━━━━━━━━━━━━━
🎯 EA: 76 (Professional)
```

#### Landing Alert (NEW!)
```
🛬 WELCOME BACK, BOS!
━━━━━━━━━━━━━━━━━
📍 Mendarat di UAE dalam 2m 0s!

📋 Post-Landing Checklist:
• Jual 8× Camel Plushie ($480,800)
• Habiskan Nerve untuk crime
• Cek stok Plushie & Flower

🎯 EA: 76/100 (Professional)
```

### 🏠 Property Market Browser
- Browse rental & selling listings per property type
- Holy Trinity filter (Airstrip + Vault + Medical Lab)
- Best Value algorithm dengan cost-to-happiness ratio
- Budget warning indicator

---

## 📁 Struktur Proyek

```
bot-torn/
├── main.py              # Entry point, Flask keep-alive, handlers registration
├── handlers.py          # Telegram command & message handlers (3000+ lines)
├── torn_api.py          # Torn API client dengan endpoint wrapper
├── scheduler.py         # APScheduler untuk background monitoring
├── crime_advisor.py     # Criminal Path Advisor (EA calculator & tips)
├── travel_data.py       # Travel Intelligence data & profit calculator
├── awards_analyzer.py   # Merit Hunter awards tracking
├── awards_reference.json # Awards database dengan API key mappings
├── groq_client.py       # Groq AI client (llama-3.3-70b-versatile)
├── config.py            # Environment variables loader
├── property_data.py     # Property types & market helpers
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
- Background scheduler untuk monitoring (60s interval)

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

## 📝 Changelog

### v4.2 (December 2024)
- ✨ **Criminal Path Advisor** - EA calculator, crime safety, tips
- ✨ **Travel Intelligence** - Profit calculator dengan Anti-Zonk
- ✨ **Departure/Landing Alerts** - Pre/Post-Flight Checklist
- ✨ **Merit Hunter** - Awards tracking dengan progress bar
- 🔧 Fixed Life bar fulltime display
- 🔧 Enhanced Baldr's Targets (6 targets, level sort, 3-3-1 layout)

### v4.0
- Multi-menu dashboard
- AI Advisor chat
- Property market browser
- Background scheduler

---

## 📝 License

Personal use only. Not affiliated with Torn City.

---

## 🤝 Credits

- **Torn City** - [torn.com](https://www.torn.com)
- **Groq** - [groq.com](https://groq.com) untuk AI model
- **Baldr** - Leveling targets database
