<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/public/logo-dark.png">
    <img src="frontend/public/logo-dark.png" width="160" alt="OmniRag Logo" style="border-radius: 32px;" />
  </picture>
</p>

<h1 align="center">OmniRag — Research Console</h1>

<p align="center">
  <strong>Ask once. Search everything.</strong><br>
  An agentic research console combining Retrieval-Augmented Generation (RAG), persistent memory, DuckDB tabular data analytics, sandboxed Python code execution, interactive charts, and 15+ live tools — completely 100% FREE.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-16.4-black?style=flat-square&logo=next.js" alt="Next.js" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Groq-Free%20Tier-f55036?style=flat-square" alt="Groq" />
  <img src="https://img.shields.io/badge/DuckDB-Analytics-fff000?style=flat-square" alt="DuckDB" />
  <img src="https://img.shields.io/badge/ChromaDB-Vector%20Store-orange?style=flat-square" alt="ChromaDB" />
</p>

---

## ✨ Features

- 🧠 **Autonomous Query Planning & Routing**: Break down complex questions into multi-step execution plans with parallel tool execution.
- ⚡ **15+ Real-Time Free Tools**: Real-time web search, Wikipedia, ArXiv research, live Yahoo Finance market quotes & history, multi-currency conversion, Open-Meteo weather & air quality, YouTube metadata & transcripts, and SEC EDGAR filings.
- 📊 **Dynamic Data & Chart Generation**: Automated bar, area, line, pie, and interactive candlestick charts generated on the fly.
- 🐍 **Sandboxed Python Sandbox**: Safe in-memory execution of Python computations, NumPy array processing, and standard output streaming without clipping or overflow.
- 🦆 **DuckDB Dataset Analytics**: Ingest CSV/XLSX spreadsheets and run instant SQL aggregations and queries.
- 🌓 **Curated Dark & Light Mode**: Complete visual parity between obsidian emerald dark mode and clean sage mint light mode, featuring dynamic theme-synced robot logos.
- 💾 **Persistent Workspace Memory**: Long-term fact storage and auto-recall for user preferences and context across research sessions.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ and pnpm

### 2. Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate   # On Windows
# source venv/bin/activate # On macOS/Linux

pip install -r requirements.txt
cp .env.example .env
# Edit .env and supply your free GROQ_API_KEY from https://console.groq.com

python run_server.py
```
Backend will run at `http://localhost:8000`.

### 3. Frontend Setup
```bash
cd frontend
pnpm install
pnpm dev
```
Open `http://localhost:3000` in your browser.

---

## 🏗️ Architecture

```
User Query (SSE Stream)
      │
      ▼
┌──────────────┐     ┌────────────────────────────────────────────────────────┐
│   FastAPI    │────▶│                 Agentic Execution Engine               │
│  /api/chat   │     │                                                        │
└──────────────┘     │  1. Query Planner (Fast JSON plan for complex tasks)   │
                     │  2. Dynamic Tool Router (Sentence-Transformers embed)  │
                     │  3. Async Model Tool Dispatch (Groq Cloud LLM)         │
                     │  4. Real-time Parallel Execution (gather)              │
                     │  5. Verification & Final Answer Synthesizer            │
                     └────────────────────────────────────────────────────────┘
```

---

## 📄 License
MIT License. Free to use and build upon.
