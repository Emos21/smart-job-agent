# KaziAI

*Kazi (Swahili) — work, job, career*

An agentic AI career platform that autonomously searches for jobs, analyzes descriptions, scores your resume against ATS systems, rewrites application materials, and preps you for interviews — all powered by multi-agent orchestration.

Built with the **ReAct pattern** (Reason → Act → Observe → Loop) — multiple specialized AI agents reason at runtime, coordinate through an orchestrator, and execute complex workflows autonomously.

## Architecture

```
                    ┌─────────────────────┐
                    │     User Input       │
                    │  (JD + Resume path)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Agent (ReAct)     │
                    │                     │
                    │  1. REASON (LLM)    │
                    │  2. ACT (tool call) │
                    │  3. OBSERVE result  │
                    │  4. Loop or finish  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
    │  JD Parser     │ │Resume Analyzer│ │Skills Matcher│
    │                │ │              │ │              │
    │ Parse text/URL │ │ Extract      │ │ Gap analysis │
    │ Extract skills │ │ sections     │ │ Match score  │
    └────────────────┘ └──────────────┘ └──────────────┘
              │                │                │
    ┌─────────▼──────┐ ┌──────▼───────┐
    │   Company      │ │ Cover Letter │
    │   Researcher   │ │ Generator    │
    │                │ │              │
    │ Fetch website  │ │ Tailored     │
    │ Get context    │ │ output       │
    └────────────────┘ └──────────────┘
```

**Key design decisions:**
- The LLM runs **at runtime** making autonomous decisions — not just at development time
- OpenAI function calling for structured tool invocation
- Agent memory tracks all reasoning steps for full context across the loop
- Each tool is independently testable via the `Tool` base class
- Deterministic tools where possible (skills matching) — LLM only where reasoning is needed

## Setup

```bash
git clone git@github.com:Emos21/smart-job-agent.git
cd smart-job-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your OpenAI API key to .env
```

## Usage

### Analyze a job description against your resume

```bash
python3 -m src.cli analyze --jd examples/sample_jd.txt --resume examples/sample_resume.txt
```

### Analyze from a URL

```bash
python3 -m src.cli analyze --jd "https://example.com/job-posting" --resume my_resume.txt --url
```

### Use a different model

```bash
python3 -m src.cli analyze --jd job.txt --resume resume.txt --model gpt-4o
```

### Search for jobs

```bash
python3 -m src.cli search --keywords "python,backend,ai" --max-results 10
```

### Use a different LLM provider

```bash
python3 -m src.cli analyze --jd job.txt --resume resume.txt --provider openai
python3 -m src.cli analyze --jd job.txt --resume resume.txt --provider deepseek
```

### List available tools

```bash
python3 -m src.cli tools
```

## Agent Tools

| Tool | Purpose |
|------|---------|
| `parse_job_description` | Extract skills, requirements, and structure from a JD (text or URL) |
| `analyze_resume` | Read and section a resume file for comparison |
| `match_skills` | Compare required/preferred skills with gap analysis and match score |
| `research_company` | Fetch company website for interview context |
| `generate_cover_letter` | Produce a tailored cover letter from analysis results |
| `search_jobs` | Search RemoteOK and Arbeitnow for matching jobs (no API key needed) |

## How the ReAct Loop Works

1. **Reason**: The LLM reads the task and all previous steps, then decides what to do next
2. **Act**: It selects a tool and provides structured arguments via OpenAI function calling
3. **Observe**: The tool executes and returns results
4. **Loop**: Results are added to memory and fed back to the LLM for the next reasoning step
5. **Finish**: When the agent has enough information, it outputs `FINAL_ANSWER` with the complete analysis

The agent typically runs 4-7 steps: parse JD → analyze resume → match skills → research company → generate cover letter → compile final analysis.

## Running Tests

```bash
python3 -m pytest tests/ -v
```

All 40 tests run without an API key — agent tests use mocked LLM responses.

## Project Structure

```
smart-job-agent/
├── src/
│   ├── agent.py              # Core ReAct agent loop
│   ├── memory.py             # Agent memory and context management
│   ├── prompts.py            # System and task prompt templates
│   ├── cli.py                # Click CLI interface
│   └── tools/
│       ├── base.py           # Tool base class and registry
│       ├── jd_parser.py      # Job description parser
│       ├── resume_analyzer.py # Resume section extractor
│       ├── skills_matcher.py # Skills gap analysis with aliases
│       ├── company_researcher.py # Company website fetcher
│       ├── cover_letter.py   # Cover letter generator
│       └── job_search.py     # Multi-source job search
├── tests/
│   ├── test_agent.py         # Agent loop tests (mocked LLM)
│   ├── test_memory.py        # Memory system tests
│   ├── test_tools.py         # Individual tool tests
│   └── test_job_search.py   # Job search tool tests
├── examples/
│   ├── sample_jd.txt         # Example job description
│   └── sample_resume.txt     # Example resume
├── requirements.txt
└── .env.example
```

## Tech Stack

- **Python 3.12** — core runtime
- **Multi-provider LLM** — Groq (free, default), OpenAI, DeepSeek via OpenAI-compatible API
- **Click** — CLI framework
- **BeautifulSoup4** — HTML parsing for URL fetching
- **Requests** — HTTP client
- **pytest** — testing framework
