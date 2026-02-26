# KaziAI

*Kazi (Swahili) — work, job, career*

An agentic AI career platform that autonomously searches for jobs, analyzes descriptions, scores your resume against ATS systems, rewrites application materials, and preps you for interviews — all powered by multi-agent orchestration.

Built with the **ReAct pattern** (Reason → Act → Observe → Loop) — multiple specialized AI agents reason at runtime, coordinate through an orchestrator, and execute complex workflows autonomously.

## Architecture

```
┌──────────────────────────────────────────────┐
│                   Frontend                    │
│         React + TypeScript + Tailwind         │
│                                              │
│  ┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐  │
│  │ Chat │ │ Search │ │Analyze │ │Tracker │  │
│  │Panel │ │ Panel  │ │ Panel  │ │ Panel  │  │
│  └──┬───┘ └───┬────┘ └───┬────┘ └───┬────┘  │
└─────┼─────────┼──────────┼──────────┼────────┘
      │         │          │          │
      ▼         ▼          ▼          ▼
┌──────────────────────────────────────────────┐
│              FastAPI Backend                   │
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │         Agentic Chat Engine              │ │
│  │  (ReAct loop with function calling)      │ │
│  │                                         │ │
│  │  LLM reasons → calls tools → observes   │ │
│  │  results → loops until answer is ready   │ │
│  └────────────────┬────────────────────────┘ │
│                   │                          │
│  ┌────────────────▼────────────────────────┐ │
│  │            Tool Registry                │ │
│  │                                         │ │
│  │ search_jobs    │ score_ats              │ │
│  │ parse_jd       │ prepare_interview      │ │
│  │ analyze_resume │ generate_cover_letter  │ │
│  │ match_skills   │ rewrite_resume         │ │
│  │ research_company                        │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │       Multi-Agent Orchestrator          │ │
│  │                                         │ │
│  │  Scout → Match → Forge → Coach          │ │
│  │  (full pipeline for deep analysis)      │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  ┌──────────┐  ┌──────┐  ┌───────────────┐  │
│  │ Auth/JWT │  │SQLite│  │ Multi-provider│  │
│  │ + OAuth  │  │  DB  │  │  LLM (Groq,   │  │
│  │          │  │      │  │  OpenAI, etc.) │  │
│  └──────────┘  └──────┘  └───────────────┘  │
└──────────────────────────────────────────────┘
```

**Key design decisions:**
- The LLM runs **at runtime** making autonomous decisions — not just at development time
- OpenAI function calling for structured tool invocation in the chat
- Multi-agent orchestrator (Scout → Match → Forge → Coach) for deep analysis pipelines
- Agent memory tracks all reasoning steps for full context across the loop
- Each tool is independently testable via the `Tool` base class
- Deterministic tools where possible (skills matching, ATS scoring) — LLM only where reasoning is needed

## Setup

```bash
git clone git@github.com:Emos21/smart-job-agent.git
cd smart-job-agent

# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your Groq API key to .env (free at console.groq.com)

# Frontend
cd frontend
npm install
npm run build
cd ..

# Run
python3 -m uvicorn src.server:app --port 8000
# Visit http://localhost:8000
```

## Features

### Agentic Chat
The chat interface uses OpenAI function calling to let the LLM autonomously decide when to use tools. Ask it to search for jobs, analyze a JD, prep for an interview — it will use the right tools and give you results grounded in real data.

### Job Search
Search across multiple free job boards (RemoteOK, Arbeitnow) with keyword matching. Save jobs to your tracker.

### Resume Analysis
Paste a job description and your resume to get:
- **ATS compatibility score** (keyword match, section completeness, formatting quality)
- **Missing keywords** to add
- **Specific improvement suggestions**

### Application Tracker
Kanban board to track applications through stages: Saved → Applied → Interview → Offer → Rejected.

### Multi-Agent Pipeline
The full pipeline dispatches 4 specialized agents in sequence:
1. **Match Agent** — analyzes JD vs resume compatibility
2. **Forge Agent** — rewrites resume bullets and generates a tailored cover letter
3. **Coach Agent** — prepares interview questions with talking points

## Usage (CLI)

```bash
# Analyze a job description against your resume
python3 -m src.cli analyze --jd examples/sample_jd.txt --resume examples/sample_resume.txt

# Search for jobs
python3 -m src.cli search --keywords "python,backend,ai" --max-results 10

# Use a different LLM provider
python3 -m src.cli analyze --jd job.txt --resume resume.txt --provider openai

# List available tools
python3 -m src.cli tools
```

## Agent Tools

| Tool | Purpose |
|------|---------|
| `search_jobs` | Search RemoteOK and Arbeitnow for matching jobs (no API key needed) |
| `parse_job_description` | Extract skills, requirements, and structure from a JD (text or URL) |
| `analyze_resume` | Read and section a resume file for comparison |
| `match_skills` | Compare required/preferred skills with gap analysis and match score |
| `score_ats` | Score resume against ATS criteria (keywords, sections, formatting) |
| `research_company` | Fetch company website for interview context |
| `generate_cover_letter` | Produce a tailored cover letter from analysis results |
| `rewrite_resume` | Reframe resume bullets to match JD language |
| `prepare_interview` | Generate interview questions with talking points by category |
| `analyze_github` | Scan GitHub profile for languages, frameworks, and portfolio strength |
| `research_salary` | Pull market salary data for a role/location/experience level |
| `draft_email` | Generate follow-up, thank-you, negotiation, and withdrawal emails |
| `generate_learning_path` | Create study plans with resources for skill gaps |
| `mock_interview` | Generate questions and evaluate answers with STAR method scoring |

## How the ReAct Loop Works

1. **Reason**: The LLM reads the user's message and conversation history, then decides what to do
2. **Act**: It selects a tool and provides structured arguments via OpenAI function calling
3. **Observe**: The tool executes and returns results
4. **Loop**: Results are fed back to the LLM for the next reasoning step (up to 3 tool rounds)
5. **Respond**: The LLM generates a natural language response grounded in the tool results

## Running Tests

```bash
python3 -m pytest tests/ -v
```

## Project Structure

```
smart-job-agent/
├── src/
│   ├── agent.py              # Core ReAct agent loop (CLI)
│   ├── server.py             # FastAPI backend with agentic chat
│   ├── database.py           # SQLite with migrations
│   ├── auth.py               # JWT + bcrypt + Google OAuth
│   ├── memory.py             # Agent memory and context management
│   ├── prompts.py            # System and task prompt templates
│   ├── cli.py                # Click CLI interface
│   ├── agents/
│   │   ├── base_agent.py     # Abstract base for specialized agents
│   │   ├── orchestrator.py   # Multi-agent pipeline coordinator
│   │   ├── scout.py          # Job search agent
│   │   ├── match.py          # JD-vs-resume analysis agent
│   │   ├── forge.py          # Cover letter / resume rewriter agent
│   │   └── coach.py          # Interview prep agent
│   └── tools/
│       ├── base.py           # Tool base class and registry
│       ├── jd_parser.py      # Job description parser
│       ├── resume_analyzer.py # Resume section extractor
│       ├── skills_matcher.py # Skills gap analysis with aliases
│       ├── ats_scorer.py     # ATS compatibility scorer
│       ├── company_researcher.py # Company website fetcher
│       ├── cover_letter.py   # Cover letter generator
│       ├── resume_rewriter.py # Resume bullet rewriter
│       ├── interview_prep.py # Interview question generator
│       ├── job_search.py     # Multi-source job search
│       ├── github_analyzer.py # GitHub portfolio scanner
│       ├── salary_research.py # Market salary data
│       ├── email_drafter.py  # Follow-up email generator
│       ├── learning_path.py  # Skill gap study plans
│       └── mock_interview.py # Mock interview with STAR evaluation
├── frontend/
│   └── src/
│       ├── App.tsx           # Root component with auth routing
│       ├── components/       # Chat, Search, Analyze, Tracker, Auth, Sidebar
│       ├── lib/api.ts        # Authenticated fetch wrapper
│       ├── hooks/            # Speech recognition hook
│       └── types/            # TypeScript interfaces
├── tests/
│   ├── test_tools.py         # Individual tool tests
│   └── test_memory.py        # Memory system tests
├── examples/
│   ├── sample_jd.txt         # Example job description
│   └── sample_resume.txt     # Example resume
├── requirements.txt
└── .env.example
```

## Tech Stack

- **Python 3.12** — core runtime
- **FastAPI + Uvicorn** — async web server
- **React + TypeScript + Tailwind CSS v4** — frontend SPA
- **Multi-provider LLM** — Groq (free, default), OpenAI, DeepSeek via OpenAI-compatible API
- **SQLite** — persistent storage with migrations
- **JWT + bcrypt** — authentication
- **Click** — CLI framework
- **BeautifulSoup4** — HTML parsing for URL fetching
- **pytest** — testing framework
