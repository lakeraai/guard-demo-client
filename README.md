# Agentic Demo - Complete Application

A sophisticated B2B sales demo platform featuring AI-powered chatbot, Lakera Guard integration, RAG capabilities, and ToolHive integration.

## 🚀 Features

- **Skinnable B2B Landing Page** with customizable branding
- **AI Chatbot** with ReAct agent architecture and smart autocomplete
- **Lakera Guard Integration** with blocking/watching modes for content moderation
- **Demo Prompt Corpus** with autocomplete functionality (right arrow key trigger)
- **RAG System** supporting file uploads and AI-generated seed packs
- **ToolHive Integration** via MCP tools
- **Admin Console** for complete configuration management
- **Export/Import** JSON skins for easy sharing

## 🏗️ Architecture

- **Frontend**: Vite + React + TypeScript + Tailwind CSS
- **Backend**: FastAPI + SQLite + ChromaDB
- **LLM**: OpenAI (chat + embeddings)
- **Vector DB**: ChromaDB for RAG
- **Security**: Lakera Guard for content moderation

## 📋 Prerequisites

- Python 3.8+
- Node.js 16+
- OpenAI API key
- Lakera API key (optional)

## 🛠️ Installation

### 1. Clone and Setup

```bash
git clone <repository-url>
cd lakeraclientdemov2
```

## 🚀 Quick Start (Recommended)

### Fastest Method: Use start_all.py

The easiest way to get started is using the `start_all.py` script, which handles most of the setup for you:

```bash
# 1. First, create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Then run the startup script
python start_all.py
```

**The script will:**
- Install all Python dependencies from `requirements.txt`
- Install all Node.js dependencies from `package.json`
- Start the backend server on port 8000
- Start the frontend server on port 3000
- Open your browser to the demo page

**Note:** You still need to create and activate the virtual environment first, but the script handles all the dependency installation and service startup for you.

## 🛠️ Manual Setup (Alternative)

If you prefer to set up the components manually or need more control:

### Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start backend server
python start_backend.py
```

### Frontend Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

### Running Both Services

**Terminal 1 - Backend:**
```bash
python start_backend.py
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

**Terminal 3 - LiteLLM (optional):**

LiteLLM runs as a separate proxy for virtual keys and model management. Default config uses `postgresql://litellm:litellm@localhost:5433/litellm` and UI login `admin` / `demo` (from `.env`).

1. **One-time setup** (from project root, with venv activated). This creates `.env` from `.env.example` if needed and generates the LiteLLM Prisma client:
   ```bash
   cp .env.example .env
   ./scripts/setup_litellm.sh
   ```

2. **If your Postgres or UI credentials differ:** edit `litellm/config.yaml` (e.g. `general_settings.database_url`) and `.env` (`UI_USERNAME`, `UI_PASSWORD`).

3. **Start the LiteLLM proxy** in Terminal 3:
   ```bash
   litellm --config litellm/config.yaml
   ```

4. Open **http://localhost:4000/ui**, sign in with `UI_USERNAME` / `UI_PASSWORD` from `.env`. Add models and mint keys there. Master key for API: `sk-demo-master-key` (or set `LITELLM_MASTER_KEY` in `.env`).

## 🌐 Access Points

- **Demo Page**: http://localhost:3000
- **Admin Console**: http://localhost:3000/admin
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (if available)
- **LiteLLM Proxy** (optional): http://localhost:4000 — **LiteLLM UI**: http://localhost:4000/ui

## ⚙️ Configuration

### 1. Initial Setup

1. Navigate to the Admin Console at http://localhost:3000/admin
2. Go to the **Security** tab
3. Enter your OpenAI API key
4. Optionally enter your Lakera API key and enable Lakera Guard
5. Configure other settings as needed

### 2. Branding Customization

In the **Branding** tab:
- Set your business name and tagline
- Upload logo and hero images
- Customize hero text

### 3. LLM Configuration

In the **LLM** tab:
- Select OpenAI model (GPT-4o, GPT-4o-mini, etc.)
- Adjust temperature (0-10 scale)
- Customize system prompt

### 4. RAG Setup

In the **RAG** tab:
- Upload documents (PDF, MD, TXT, CSV)
- Generate AI-powered seed packs
- View ingested content

### 5. Tool Management

In the **Tools** tab:
- Add custom tools
- Configure MCP endpoints
- Test tool functionality

### 6. Demo Prompt Corpus

In the **Demo Prompts** tab:
- Create curated demo prompts for different scenarios
- Organize prompts by category (general, security, tools, rag, malicious)
- Add tags for easy searching
- Mark prompts as malicious for security testing
- Track usage statistics

**Chat Autocomplete:**
- Start typing in the chat (minimum 2 characters)
- See real-time suggestions with autocomplete overlay
- Press **right arrow key (→)** to complete the current suggestion
- Click on suggestions in the dropdown to select them
- Escape key to dismiss suggestions

## 🔧 API Endpoints

### Config
- `GET /config` - Get current configuration
- `PUT /config` - Update configuration
- `POST /config/export` - Export config as JSON
- `POST /config/import` - Import config from JSON

### Chat
- `POST /chat` - Send message to AI assistant

### RAG
- `POST /rag/upload` - Upload documents
- `POST /rag/generate` - Generate AI content
- `GET /rag/search` - Search stored content

### Tools
- `GET /tools` - List tools
- `POST /tools` - Create tool
- `PUT /tools/{id}` - Update tool
- `DELETE /tools/{id}` - Delete tool
- `POST /tools/test/{id}` - Test tool

### Lakera
- `GET /lakera/last` - Get last guardrail result

### Demo Prompts
- `GET /demo-prompts` - List demo prompts
- `GET /demo-prompts/search` - Search demo prompts with autocomplete
- `POST /demo-prompts` - Create demo prompt
- `PUT /demo-prompts/{id}` - Update demo prompt
- `DELETE /demo-prompts/{id}` - Delete demo prompt
- `POST /demo-prompts/{id}/use` - Track prompt usage

## 📁 Project Structure

```
lakeraclientdemov2/
├── backend/                 # FastAPI backend
│   ├── __init__.py
│   ├── main.py             # FastAPI app
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   ├── database.py         # Database connection
│   ├── openai_client.py    # OpenAI integration
│   ├── rag.py             # RAG service
│   ├── lakera.py          # Lakera integration
│   ├── toolhive.py        # ToolHive service
│   └── agent.py           # ReAct agent
├── src/                    # React frontend
│   ├── components/         # React components
│   │   ├── ChatWidget.tsx  # Chat with autocomplete
│   │   ├── DemoPromptManager.tsx # Prompt management
│   │   └── ...
│   ├── pages/             # Page components
│   ├── services/          # API services
│   ├── types/             # TypeScript types
│   └── ...
├── data/                   # Data storage
│   ├── agentic_demo.db    # SQLite database
│   └── chroma/            # ChromaDB vectors
├── uploads/               # Uploaded files
├── exports/               # Exported configs
├── requirements.txt       # Python dependencies
├── package.json          # Node.js dependencies
├── start_backend.py      # Backend startup script
└── README.md             # This file
```

## 🎯 Demo Features

### Chat Interface
- Real-time chat with AI assistant
- Smart autocomplete with demo prompt corpus
- Tool usage tracking
- Lakera guardrail monitoring
- Message history

### Lakera Integration
- Content moderation with blocking/watching modes
- Guardrail enforcement (blocking mode) or monitoring (watching mode)
- Real-time status monitoring
- Detailed violation reporting with TL;DR summaries

### RAG Capabilities
- Document upload (PDF, MD, TXT, CSV)
- AI-generated content creation
- Semantic search
- Content chunking and embedding

### Tool Integration
- Calculator tool
- HTTP fetch tool
- Calendar lookup
- GitHub repository info
- Custom tool addition

### Demo Prompt Corpus
- Curated prompt library for consistent demos
- Category-based organization (general, security, tools, rag, malicious)
- Tag-based search and filtering
- Usage tracking and analytics
- Smart autocomplete in chat interface
- Right arrow key (→) completion trigger
- Visual indicators for malicious prompts
- Admin interface for prompt management

## 🔒 Security Features

- API key masking in UI
- Secure file upload validation
- Content moderation via Lakera
- Input sanitization
- CORS configuration

## 📦 Export/Import

### Export Configuration
1. Go to Admin Console → Export/Import
2. Click "Export Config"
3. Download JSON file with all settings

### Import Configuration
1. Go to Admin Console → Export/Import
2. Upload previously exported JSON file
3. Configuration will be restored

## 🐛 Troubleshooting

### Common Issues

1. **Backend won't start**
   - Check Python version (3.8+)
   - Verify all dependencies installed
   - Check port 8000 availability

2. **Frontend won't start**
   - Check Node.js version (16+)
   - Run `npm install`
   - Check port 3000 availability

3. **API errors**
   - Verify OpenAI API key is set
   - Check network connectivity
   - Review browser console for CORS issues

4. **Database issues**
   - Delete `data/` folder to reset
   - Check file permissions
   - Verify SQLite installation

### Logs

- Backend logs: Check terminal running `start_backend.py`
- Frontend logs: Check browser console
- API logs: Check backend terminal output

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Check the browser console for errors
3. Review backend logs in the terminal
4. Check the API endpoints in the code if needed

---

**Happy Demo-ing! 🎉**
