# Quickstart Guide

Get TravelOps AI up and running on your local machine in under 5 minutes.

---

## 🛠️ Step 1: Clone and Set Up Environment

Ensure Python 3.10+ and Node.js 18+ are installed.

```bash
# Clone the repository
git clone https://github.com/Dolendra/TravelOps-AI-Autonomous-Travel-Operations-Agent.git
cd TravelOps-AI-Autonomous-Travel-Operations-Agent

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 🔑 Step 2: Configure Environment Variables

Copy the configuration template:

```bash
cp .env.example .env
```

Open `.env` and fill in your keys (especially the `GROQ_API_KEY` for LLM agent reasoning):
```env
GROQ_API_KEY=gsk_your_groq_key_here
JWT_SECRET_KEY=generate_a_secure_hex_key_here
```

---

## 🗄️ Step 3: Initialize and Seed Database

Run the reset and seeding commands to prepare your SQLite database with 100+ bookings, logs, and routing metrics:

```bash
# Drop, recreate, and seed default bus lines
python scripts/reset_db.py

# Seed the full 100 bookings demo dataset
python scripts/seed_demo_dataset.py
```

---

## 🚀 Step 4: Run the Servers

Start the backend and frontend dev servers:

### 1. Start backend FastAPI Server (Port 8000)
```bash
python -m uvicorn backend.api.main:app --port 8000 --reload
```

### 2. Start frontend React Client (Port 5173)
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

- **Developer / Admin Logins**:
  Use `admin@travelops.ai` or register a new administrator account in the authentication modal.

---

## 🧪 Step 5: Verify the Ecosystem

Run the automated test suite to ensure the runtime compilation and provider failover rules are working:

```bash
pytest
```
