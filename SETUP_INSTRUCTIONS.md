# Setup Instructions – guard-demo-client

Step-by-step from the README. Do these in order.

---

## Prerequisites (install if needed)

- **Python 3.8–3.12** – `python3 --version` (3.13/3.14 not yet supported by some deps, e.g. pandas; use `pyenv install 3.12` or Homebrew `python@3.12` if needed)
- **Node.js 16+** – `node --version`
- **OpenAI API key** – from https://platform.openai.com
- **Lakera API key** (optional) – for content moderation
- **PostgreSQL** (only if you use LiteLLM) – default config expects `localhost:5433`

---

## Option A: Quick start (one script)

1. **Open the project in Cursor**  
   File → Open Folder → select `guard-demo-client`.

2. **Create and activate a virtual environment**
   ```bash
   cd /Users/teddya/demo-project/guard-demo-client
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

3. **Run the startup script**
   ```bash
   python start_all.py
   ```
   This will:
   - Install Python deps from `requirements.txt`
   - Install Node deps from `package.json`
   - Start backend on **port 8000**
   - Start frontend on **port 3000**
   - Open the demo in your browser

4. **Configure the app**
   - Open **http://localhost:3000/admin**
   - **Security** tab: add your **OpenAI API key** (required); optionally Lakera API key
   - Use other tabs for branding, LLM, RAG, tools, demo prompts

---

## Option B: Manual setup (two terminals)

**Terminal 1 – Backend**

```bash
cd /Users/teddya/demo-project/guard-demo-client
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python start_backend.py
```

**Terminal 2 – Frontend**

```bash
cd /Users/teddya/demo-project/guard-demo-client
npm install
npm run dev
```

Then open http://localhost:3000 and http://localhost:3000/admin and add your OpenAI key in Admin → Security.

---

## Optional: LiteLLM proxy (Terminal 3)

Only if you want the LiteLLM proxy for virtual keys and model management.

1. **PostgreSQL**  
   Default config uses: `postgresql://litellm:litellm@localhost:5433/litellm`.  
   Create that DB and user, or change the URL in `litellm/config.yaml`.

2. **One-time setup** (from project root, with venv activated)
   ```bash
   cp .env.example .env
   ./scripts/setup_litellm.sh
   ```
   Edit `.env` if you want different `UI_USERNAME` / `UI_PASSWORD`.  
   Edit `litellm/config.yaml` → `general_settings.database_url` if your Postgres is different.

3. **Start LiteLLM** (e.g. Terminal 3)
   ```bash
   source venv/bin/activate
   litellm --config litellm/config.yaml
   ```

4. **Use the UI**  
   Open **http://localhost:4000/ui**, sign in with `UI_USERNAME` / `UI_PASSWORD` from `.env`. Add models and create keys. API master key: `sk-demo-master-key` (or set `LITELLM_MASTER_KEY` in `.env`).

5. **Lakera Guard (optional)**  
   To enable content moderation (prompt injection, PII, etc.) on proxy requests, add your Lakera API key to `.env`:
   ```bash
   export LAKERA_API_KEY=your-lakera-api-key
   ```
   Then `source .env` before starting LiteLLM. The guardrail runs on every request (`default_on: true`). Get a key at [platform.lakera.ai](https://platform.lakera.ai).  
   Note: Lakera v2 is documented for `/v1/chat/completions`; Claude Code uses `/v1/messages`—guardrail support may vary.

---

## URLs

| What            | URL                        |
|-----------------|----------------------------|
| Demo            | http://localhost:3000      |
| Admin console   | http://localhost:3000/admin |
| Backend API     | http://localhost:8000      |
| API docs        | http://localhost:8000/docs |
| LiteLLM (opt.) | http://localhost:4000      |
| LiteLLM UI      | http://localhost:4000/ui   |

---

## Troubleshooting

- **Backend won’t start** – Python 3.8+, port 8000 free, `pip install -r requirements.txt`.
- **Frontend won’t start** – Node 16+, port 3000 free, `npm install`.
- **API errors** – Set OpenAI API key in Admin → Security.
- **DB issues** – Remove `data/` to reset SQLite.
