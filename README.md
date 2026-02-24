# Smart Job Agent

An agentic AI system that autonomously analyzes job descriptions, matches them against your resume, and generates tailored application materials.

Built with the **ReAct pattern** (Reason → Act → Observe → Loop) — the LLM reasons at runtime, selects tools, and executes multi-step workflows autonomously.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your OpenAI API key to .env
```

## Usage

```bash
python -m src.cli analyze --jd examples/sample_jd.txt --resume examples/sample_resume.txt
```
