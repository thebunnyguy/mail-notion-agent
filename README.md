# 📬 Mail + Google Groups → Notion Summarization Agent

Reads your **Gmail inbox** and **Google Groups posts** (directly, not via Gmail),
summarizes them using **NVIDIA NIM's free LLM API** (`nvidia/llama-3.1-nemotron-70b-instruct`),
and publishes clean summaries to your **Notion workspace** — 5× daily.

---

## 🚀 Quick Setup (5 steps)

### Step 1 — Install Python dependencies

```bash
cd mail_notion
pip install -r requirements.txt
```

---

### Step 2 — Set up NVIDIA NIM API key (free)

1. Go to [build.nvidia.com](https://build.nvidia.com) and **sign up for free**
2. Click **"Get API Key"** from any model page
3. Copy your `nvapi-...` key

---

### Step 3 — Set up Google Cloud (Gmail + Groups access)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or reuse one)
3. Go to **APIs & Services → Enable APIs**:
   - Enable **Gmail API**
4. Go to **APIs & Services → Credentials**:
   - Click **Create Credentials → OAuth 2.0 Client IDs**
   - Application type: **Desktop app**
   - Download the JSON → rename it `google_credentials.json`
   - Save it to `credentials/google_credentials.json`
5. Go to **OAuth consent screen** → add your Gmail address as a **Test user**

> **First run only**: A browser window will open asking you to log in with your Google account and approve access. This is one-time only — token is saved to `credentials/token.json`.

---

### Step 4 — Set up Notion Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Give it a name (e.g. "Mail Summary Agent"), select your workspace
4. Copy the **Integration Token** (`secret_...`)
5. Open the Notion **Database** where summaries should be published:
   - Click **"..."** → **"Add connections"** → select your integration
   - Copy the **Database ID** from the URL:
     ```
     https://notion.so/yourworkspace/{DATABASE_ID}?v=...
     ```
     The ID is the 32-character string before `?v=`

---

### Step 5 — Create `.env` and configure

```bash
cp .env.example .env
```

Edit `.env` with your actual keys:
```env
NVIDIA_API_KEY=nvapi-your-actual-key-here
NOTION_API_KEY=secret_your-actual-key-here
NOTION_DATABASE_ID=your-32-char-database-id
```

Then edit `config.yaml` to set your Google Groups and preferences:
```yaml
google_groups:
  groups:
    - your-group-name   # e.g. "myteam-devs" from myteam-devs@googlegroups.com
```

---

## 🎮 Usage

```bash
# Test run — fetches + summarizes, prints output, does NOT publish to Notion
python main.py --test

# Run once immediately — fetches, summarizes, and publishes to Notion
python main.py --run-now

# Start the full scheduler — runs at 9am, 12:30pm, 3pm, 6pm, 9pm IST
python main.py
```

---

## 📁 Project Structure

```
mail_notion/
├── main.py                   # Entry point + scheduler
├── config.yaml               # Your preferences (edit this!)
├── .env                      # API keys (never commit this)
├── .env.example              # Template for .env
├── requirements.txt
├── README.md
│
├── credentials/
│   ├── google_credentials.json   ← YOU download this from Google Cloud
│   └── token.json                ← Auto-created on first run
│
├── agents/
│   ├── gmail_agent.py        # Fetches Gmail inbox
│   ├── groups_agent.py       # Fetches Google Groups (RSS + HTML)
│   ├── summarizer.py         # NVIDIA NIM LLM call
│   └── notion_agent.py       # Publishes to Notion
│
├── utils/
│   ├── formatter.py          # Builds LLM prompts
│   └── logger.py             # Logging to console + logs/
│
└── logs/                     # Auto-created; daily log files
```

---

## ⚙️ Customization

All preferences live in `config.yaml`:

| Setting | What it does |
|---|---|
| `gmail.time_window_hours` | How far back to fetch emails per run |
| `gmail.priority_senders` | Focus on emails from specific addresses |
| `gmail.exclude_senders` | Skip newsletters, noreply, etc. |
| `google_groups.groups` | List of Google Group names to monitor |
| `summary.focus_topics` | Topics you care about (LLM prioritizes these) |
| `summary.style` | `bullet_points`, `paragraph`, or `tldr` |
| `schedule.times` | When to run each day (24h format, IST) |

---

## 🔒 Security Notes

- **Never commit `.env` or `credentials/token.json`** to version control
- The agent requests `gmail.readonly` scope only — it **cannot** send, delete, or modify emails
- NVIDIA NIM processes your email content — don't use if you have strict data privacy requirements

---

## 🤖 Model Info

**`nvidia/llama-3.1-nemotron-70b-instruct`**
- NVIDIA's fine-tuned Llama 3.1 70B
- 128K context window (handles large email volumes)
- Free tier: ~1000 credits/month on build.nvidia.com
- OpenAI-compatible API at `https://integrate.api.nvidia.com/v1`
