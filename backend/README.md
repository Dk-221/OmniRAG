<p align="center">
  <img src="logo.png" width="140" alt="OmniRag Logo" style="border-radius: 28px;" />
</p>

# OmniRag Backend – Agentic RAG with Real-Time Tools

A production-ready agentic AI backend that combines **Retrieval-Augmented Generation (RAG)**, persistent **memory**, **sandboxed Python execution**, **DuckDB data analysis**, **chart generation**, and **15+ live real-time tools** — all completely **100% FREE** with **no paid tiers** or paid APIs.

Built with: **FastAPI + Groq Cloud (free tier) + ChromaDB + sentence-transformers + DuckDB + trafilatura + yfinance + Open-Meteo**

---

## Architecture

```
User Request (SSE Stream)
     │
     ▼
┌─────────────┐     ┌────────────────────────────────────────────────────────┐
     FastAPI   │────▶│                 Agentic Execution Engine               │
  /api/chat   │     │                                                        │
└─────────────┘     │  1. Query Planner (Groq fast JSON plan for complex Qs) │
                    │     {"type":"plan"} -> {"type":"plan_step"}            │
                    │                                                        │
                    │  2. Dynamic Tool Router (Sentence-Transformers + KWs)  │
                    │     Filters 20 tools down to <=6 for Groq Free Tier   │
                    │                                                        │
                    │  3. Model Tool Dispatch (openai/gpt-oss-20b)           │
                    │     ├── Concurrency: asyncio.gather parallel tools     │
                    │     ├── Artifacts: {"type":"artifact"} (chart/table)   │
                    │     └── Tool Results: {"type":"tool_result"}           │
                    │                                                        │
                    │  4. Self-Check Verification (toggleable)              │
                    │     Checks claims vs evidence: {"type":"verification"} │
                    │                                                        │
                    │  5. Final Streaming Output: {"type":"token"}, sources  │
                    └────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   ChromaDB Store   │  ← Local persistent vector store
                    │   ├── knowledge_base│  ← Document chunks + page metadata
                    │   └── memories     │  ← User facts & persistent memory
                    └────────────────────┘
```

---

## ⚠️ Python Sandbox Warning & Security

The `run_python` tool executes code in an isolated subprocess sandbox:
- **10-Second Execution Timeout**: Subprocesses are automatically killed after 10s.
- **Blocked System Modules**: Direct imports of dangerous libraries (`os`, `sys`, `subprocess`, `socket`, `shutil`, `importlib`, `ctypes`, `threading`, `multiprocessing`, `urllib`, `requests`, `httpx`) are blocked at runtime.
- **Isolated Temp Directory**: Scripts execute in disposable temporary directories.
- **Allowed Safe Libraries**: `math`, `statistics`, `json`, `datetime`, `pandas`, `numpy`.
- **Precaution**: While protected against casual escapes, running untrusted model-generated code should always be isolated in containers or sandboxed environments in enterprise production deployments.

---

## All 20 Registered Tools (By Category)

| Tool | Category | Description | Key Required |
|------|----------|-------------|--------------|
| `search_knowledge_base` | knowledge | Semantic similarity search over uploaded documents and saved memories | None |
| `remember` | knowledge | Store a user-provided fact or preference into persistent Chroma memory | None |
| `web_search` | web | Live web search via DuckDuckGo | None |
| `read_url` | web | SSRF-safe webpage reader with trafilatura main-text extraction | None |
| `wikipedia_lookup` | web | Wikipedia REST API topic lookup and summary | None |
| `search_papers` | web | Academic paper search via arXiv public Atom API (max 5 results) | None |
| `tech_news` | web | Hacker News stories and search via Algolia API | None |
| `get_news` | web | Google News RSS feed for breaking news parsed with feedparser | None |
| `youtube_summary` | web | YouTube video transcript extraction via youtube-transcript-api | None |
| `get_stock_data` | finance | Real-time equity data via yfinance (US + Indian .NS/.BO stocks) | None |
| `compare_stocks` | finance | Multi-stock historical performance (2-4 tickers) with normalized line chart artifact | None |
| `currency_convert` | finance | Live exchange rates and currency conversion via Frankfurter API | None |
| `crypto_price` | finance | Real-time crypto prices in USD and INR via CoinGecko | None |
| `analyze_data` | data | Local SQL analysis of uploaded CSV/XLSX using DuckDB | None |
| `make_chart` | data | Structured chart spec validator for bar, line, pie, and area artifacts | None |
| `run_python` | code | Sandboxed Python code execution with 10s timeout and result capture | None |
| `calculate` | utility | Safe AST-based mathematical expression evaluator | None |
| `get_weather` | utility | Current weather and 3-day forecast via Open-Meteo | None |
| `air_quality` | utility | US AQI, PM2.5, PM10, and health advisories via Open-Meteo | None |
| `geocode_place` | utility | OpenStreetMap Nominatim geocoding (rate-limited to 1 req/sec) | None |

---

## Windows Setup (Step-by-Step)

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- Powershell

### 2. Virtual Environment & Dependencies

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```
Fill in your free Groq key from [console.groq.com](https://console.groq.com):
```env
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-20b
GROQ_FALLBACK_MODEL=openai/gpt-oss-120b
VERIFY_ANSWERS=true
ROUTER_MAX_TOOLS=6
```

### 4. Run the Server

```powershell
python main.py
# Server runs at http://localhost:8000
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check, active model, document chunk counts, verification settings |
| `GET` | `/api/tools` | List all 20 registered tools with `{name, description, category}` |
| `POST` | `/api/chat` | Main SSE streaming chat endpoint |
| `POST` | `/api/upload` | Upload PDF/TXT/MD document to knowledge base |
| `POST` | `/api/ingest` | Re-index all knowledge base documents |
| `GET` | `/api/documents` | List indexed documents and chunk statistics |
| `GET` | `/api/documents/{filename}/page/{n}` | Retrieve extracted text for page `n` of a document for source viewing |
| `POST` | `/api/data/upload` | Upload CSV or XLSX dataset for DuckDB analysis |
| `GET` | `/api/data/files` | List all uploaded dataset files |
| `GET` | `/api/memories` | Retrieve all persistent memories stored by the agent |
| `DELETE` | `/api/memories/{id}` | Delete a stored memory by ID |

---

## SSE Event Contract

Every SSE message emitted on `/api/chat` is a JSON line (`data: {...}\n\n`):

- **Plan**: `{"type":"plan","steps":[{"id":1,"text":"..."}]}`
- **Plan Step**: `{"type":"plan_step","id":1,"status":"running|done"}`
- **Tool Call**: `{"type":"tool_call","id":"call_123","name":"...","args":{...}}`
- **Tool Result**: `{"type":"tool_result","id":"call_123","name":"...","summary":"...","ok":true,"artifact_ref":"call_123"}`
- **Artifact**: `{"type":"artifact","kind":"chart|table|stock|weather|news|code","tool_call_id":"call_123","data":{...}}`
- **Verification**: `{"type":"verification","verdict":"supported|partial|unsupported","notes":"..."}`
- **Tokens**: `{"type":"token","text":"..."}`
- **Sources**: `{"type":"sources","items":[{"type":"doc|web|news|finance","title":"...","ref":"...","page":1}]}`
- **Done**: `{"type":"done"}`

### Artifact Shapes

- **chart**: `{"chart_type":"bar|line|pie|area","title":"...","labels":[...],"series":[{"name":"...","data":[...]}]}`
- **table**: `{"columns":[...],"rows":[[...]]}`
- **stock**: `{"ticker":"...","price":123.4,"change_pct":1.2,"day_low":120.0,"day_high":125.0,"currency":"USD"}`
- **weather**: `{"city":"...","current_temp":22.0,"condition":"Sunny","forecast":[{"day":"...","min":15,"max":25,"condition":"..."}]}`
- **news**: `{"items":[{"title":"...","source":"...","published":"...","url":"..."}]}`
- **code**: `{"code":"...","stdout":"...","error":null}`

---

## 12 Test Questions (Covering All Tools & Multi-Tool Combinations)

### 1. 📊 Data Analysis (DuckDB SQL)
> *"Upload `sales.csv` and calculate the total revenue and average order value by region."*
- **Tools**: `analyze_data`

### 2. 📈 Stock Performance & Line Chart
> *"Compare AAPL and RELIANCE.NS over 6 months and chart it."*
- **Tools**: `compare_stocks` (emits line chart artifact)

### 3. 🐍 Sandboxed Python Execution
> *"Run Python to compute the first 25 Fibonacci numbers and calculate the golden ratio approximation."*
- **Tools**: `run_python` (emits code artifact)

### 4. 🌐 SSRF-Safe Web Page Reading
> *"Read the article at https://en.wikipedia.org/wiki/Artificial_intelligence and summarize its section on Ethics."*
- **Tools**: `read_url`

### 5. 📺 YouTube Video Summarizer
> *"Summarize the transcript of the video at https://www.youtube.com/watch?v=dQw4w9WgXcQ."*
- **Tools**: `youtube_summary`

### 6. 📚 Academic Papers (arXiv)
> *"Search recent research papers on 'Generative Diffusion Models for Audio' and list their abstracts."*
- **Tools**: `search_papers`

### 7. 💻 Tech News & Algolia Hacker News
> *"What are the top trending stories on Hacker News right now regarding open-source LLMs?"*
- **Tools**: `tech_news`

### 8. 📰 Google News RSS & Breaking Events
> *"What are the latest news headlines about renewable energy investments in India?"*
- **Tools**: `get_news` (emits news artifact)

### 9. 💱 Currency Conversion & Crypto Tracker
> *"What is the current price of Ethereum in INR, and convert 500 EUR to INR."*
- **Tools**: `crypto_price` + `currency_convert`

### 10. 🌤️ Weather, Air Quality & Geocoding
> *"What is the air quality AQI and current weather forecast for Tokyo, Japan?"*
- **Tools**: `air_quality` + `get_weather` + `geocode_place`

### 11. 🧠 Persistent Memory & Recall
> *"Remember that my target portfolio allocation is 60% equities and 40% fixed income. Then confirm what you remember."*
- **Tools**: `remember` + `search_knowledge_base`

### 12. 🔗 Comprehensive Multi-Tool Chain
> *"Check the stock price of TCS.NS, find the latest news headlines about Tata Consultancy Services, and chart a comparison between TCS.NS and INFY.NS over 3 months."*
- **Tools**: `get_stock_data` + `get_news` + `compare_stocks` (parallel execution)

---

## Running Automated Tests

```powershell
# Run original test suite (all 11 passed)
.\venv\Scripts\python.exe -m pytest tests/test_tools.py -v

# Run new tools smoke tests (all 17 passed)
.\venv\Scripts\python.exe -m pytest tests/test_new_tools.py -v

# Run End-to-End Chat verification
.\venv\Scripts\python.exe tests/test_e2e.py
```

---

## License

MIT – Free to use, modify, and distribute.
