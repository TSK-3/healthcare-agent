# Healthcare Voice Intake System

An AI-powered voice agent that automates patient intake interviews. Upload a healthcare form as a PDF, let the system extract the questions, and have a voice agent call patients and record their responses automatically.

---

## What It Does

A doctor uploads a healthcare intake PDF. The system reads it, identifies all the questions, and a voice agent conducts a live phone-style interview with the patient. Every answer is saved to a PostgreSQL database as a single structured record per call.

---

## Project Structure

```
healthcare-intake/
│
├── extractor.py              # Reads PDF and extracts questions using LangChain + Groq
├── questions.json            # Output from extractor — list of questions for the agent
│
├── healthcare-agent/
│   ├── src/
│   │   └── agent.py          # LiveKit voice agent — runs the patient interview
│   ├── questions/
│   │   ├── general.json      # General intake questions
│   │   ├── cardiology.json   # Cardiology-specific questions
│   │   ├── ophthalmology.json
│   │   └── pediatrics.json
│   ├── .env.local            # API keys (not committed to git)
│   └── pyproject.toml
│
└── README.md
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| PDF Reading | pdfplumber |
| Question Extraction | LangChain + Groq LLaMA 3.3 70B |
| Voice Infrastructure | LiveKit Agents |
| Speech to Text | Deepgram Nova-2 |
| AI Brain | Groq LLaMA 3.3 70B |
| Text to Speech | Deepgram Aura |
| Voice Detection | Silero VAD |
| Database | PostgreSQL on Neon |

---

## Setup

### 1. Clone the repo and create a virtual environment

```bash
git clone https://github.com/your-username/healthcare-intake.git
cd healthcare-intake
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux
```

### 2. Install dependencies

```bash
pip install pdfplumber langchain langchain-groq python-dotenv psycopg2-binary
pip install livekit-agents livekit-plugins-groq livekit-plugins-deepgram livekit-plugins-silero livekit-plugins-turn-detector
```

### 3. Set up API keys

Create a `.env.local` file inside the `healthcare-agent/` folder:

```
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret
GROQ_API_KEY=your-groq-api-key
DEEPGRAM_API_KEY=your-deepgram-api-key
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

Create a `.env` file in the root folder (for the extractor):

```
GROQ_API_KEY=your-groq-api-key
```

### 4. Set up the database

In your Neon SQL editor (or any PostgreSQL client), run:

```sql
CREATE TABLE answers (
    id           SERIAL PRIMARY KEY,
    room_id      TEXT,
    department   TEXT,
    conversation JSONB,
    created_at   TIMESTAMP DEFAULT NOW()
);
```

---

## Usage

### Step 1 — Extract questions from your PDF

Place your healthcare intake PDF in the root folder and run:

```bash
python extractor.py
```

This will generate `questions.json` with all identified questions. Copy it into the `healthcare-agent/` folder.

### Step 2 — Start the voice agent

```bash
cd healthcare-agent
python src/agent.py dev
```

You should see:
```
✅ Loaded N questions
✅ Connected to PostgreSQL!
✅ Registered worker — healthcare-agent
```

### Step 3 — Test the agent

Go to [agents-playground.livekit.io](https://agents-playground.livekit.io), connect using your LiveKit credentials, and start talking. The agent will greet you and begin asking intake questions.

### Step 4 — View saved answers

In your Neon dashboard, run:

```sql
SELECT room_id, department, created_at FROM answers ORDER BY created_at DESC;
```

To view a full conversation:

```sql
SELECT conversation FROM answers WHERE room_id = 'your-room-id';
```

---

## How It Works

```
Patient joins call
      ↓
Agent loads questions.json
      ↓
Asks questions one by one via voice
      ↓
Patient answers by speaking
      ↓
Deepgram STT converts speech to text
      ↓
Groq LLM generates next question
      ↓
Deepgram TTS speaks it aloud
      ↓
Call ends → full conversation saved to PostgreSQL
```

---

## Environment Variables Reference

| Variable | Where to get it |
|----------|----------------|
| `LIVEKIT_URL` | cloud.livekit.io → Project Settings |
| `LIVEKIT_API_KEY` | cloud.livekit.io → Project Settings |
| `LIVEKIT_API_SECRET` | cloud.livekit.io → Project Settings |
| `GROQ_API_KEY` | console.groq.com → API Keys |
| `DEEPGRAM_API_KEY` | console.deepgram.com → API Keys |
| `DATABASE_URL` | neon.tech → Project → Connection String |

---

## Database Schema

```sql
answers (
    id           SERIAL PRIMARY KEY,
    room_id      TEXT,         -- unique LiveKit session ID
    department   TEXT,         -- patient department (general, cardiology, etc.)
    conversation JSONB,        -- full conversation as JSON array
    created_at   TIMESTAMP     -- when the call happened
)
```

Each conversation record looks like:

```json
[
  { "role": "agent",   "text": "Hello! I am your healthcare assistant.", "time": "2026-05-26T10:00:01" },
  { "role": "patient", "text": "Hi",                                     "time": "2026-05-26T10:00:04" },
  { "role": "agent",   "text": "Do you currently have chest pain?",      "time": "2026-05-26T10:00:06" },
  { "role": "patient", "text": "No I don't",                             "time": "2026-05-26T10:00:11" }
]
```

---
