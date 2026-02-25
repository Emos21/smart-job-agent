import os
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

from . import database as db
from .tools.job_search import JobSearchTool
from .tools.jd_parser import JDParserTool
from .tools.resume_analyzer import ResumeAnalyzerTool
from .tools.skills_matcher import SkillsMatcherTool
from .tools.ats_scorer import ATSScorerTool
from .tools.interview_prep import InterviewPrepTool
from .agents.orchestrator import Orchestrator

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="KaziAI",
    description="AI-powered career platform with multi-agent orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve React frontend static files
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")


# --- Request/Response Models ---

class SearchRequest(BaseModel):
    keywords: list[str]
    max_results: int = 10


class AnalyzeRequest(BaseModel):
    jd_text: str
    resume_path: str = "examples/sample_resume.txt"


class PipelineRequest(BaseModel):
    jd_text: str
    resume_path: str = "examples/sample_resume.txt"
    role: str = "Software Engineer"
    company: str = "the company"


class SaveJobRequest(BaseModel):
    title: str
    company: str
    location: str = ""
    url: str = ""
    source: str = ""
    tags: list[str] = []


class UpdateApplicationRequest(BaseModel):
    status: str | None = None
    notes: str | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


class RenameConversationRequest(BaseModel):
    title: str


# --- API Routes ---

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "KaziAI"}


@app.post("/api/search")
def search_jobs(req: SearchRequest):
    """Search for jobs across multiple boards."""
    tool = JobSearchTool()
    result = tool.execute(keywords=req.keywords, max_results=req.max_results)
    return result


@app.post("/api/analyze")
def analyze_job(req: AnalyzeRequest):
    """Analyze a JD against a resume using the Match agent pipeline."""
    # Parse JD
    jd_tool = JDParserTool()
    jd_result = jd_tool.execute(source=req.jd_text)

    # Read resume
    resume_tool = ResumeAnalyzerTool()
    resume_result = resume_tool.execute(file_path=req.resume_path)

    if not resume_result.get("success"):
        raise HTTPException(status_code=400, detail=resume_result.get("error"))

    # ATS Score
    jd_keywords = []
    for section in jd_result.get("sections", {}).values():
        words = section.split()
        jd_keywords.extend([w.strip(",-.:;") for w in words if len(w) > 3])
    jd_keywords = list(set(jd_keywords))[:30]

    ats_tool = ATSScorerTool()
    ats_result = ats_tool.execute(
        resume_text=resume_result.get("raw_text", ""),
        jd_keywords=jd_keywords,
    )

    return {
        "jd_analysis": jd_result,
        "resume_analysis": resume_result,
        "ats_score": ats_result,
    }


@app.post("/api/pipeline")
def run_pipeline(req: PipelineRequest):
    """Run the full multi-agent pipeline (Match → Forge → Coach)."""
    # Read resume text
    resume_tool = ResumeAnalyzerTool()
    resume_result = resume_tool.execute(file_path=req.resume_path)

    if not resume_result.get("success"):
        raise HTTPException(status_code=400, detail=resume_result.get("error"))

    orchestrator = Orchestrator(provider="groq")
    result = orchestrator.full_pipeline(
        jd_text=req.jd_text,
        resume_path=req.resume_path,
        resume_text=resume_result.get("raw_text", ""),
        role=req.role,
        company=req.company,
    )

    return {
        "analysis": result["analysis"],
        "materials": result["materials"],
        "interview_prep": result["interview_prep"],
    }


@app.post("/api/jobs/save")
def save_job(req: SaveJobRequest):
    """Save a job to the tracker."""
    job_id = db.save_job(req.model_dump())
    return {"id": job_id, "message": "Job saved"}


@app.get("/api/jobs")
def list_jobs():
    """Get all saved jobs."""
    return db.get_jobs()


@app.post("/api/applications/{job_id}")
def create_application(job_id: int, jd_text: str = ""):
    """Create an application for a saved job."""
    app_id = db.create_application(job_id, jd_text)
    return {"id": app_id, "message": "Application created"}


@app.get("/api/applications")
def list_applications(status: str | None = None):
    """Get all applications, optionally filtered by status."""
    return db.get_applications(status)


@app.patch("/api/applications/{app_id}")
def update_application(app_id: int, req: UpdateApplicationRequest):
    """Update an application's status or notes."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    db.update_application(app_id, **updates)
    return {"message": "Updated"}


# --- Conversation endpoints ---

@app.get("/api/conversations")
def list_conversations():
    """Get all conversations, most recent first."""
    return db.get_conversations()


@app.post("/api/conversations")
def create_conversation_endpoint():
    """Create a new empty conversation."""
    conv_id = db.create_conversation("New Chat")
    conv = db.get_conversation(conv_id)
    return conv


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int):
    """Delete a conversation and all its messages."""
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete_conversation(conv_id)
    return {"message": "Conversation deleted"}


@app.patch("/api/conversations/{conv_id}")
def rename_conversation(conv_id: int, req: RenameConversationRequest):
    """Rename a conversation."""
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.update_conversation_title(conv_id, req.title)
    return {"message": "Conversation renamed"}


@app.get("/api/conversations/{conv_id}/messages")
def get_conversation_messages(conv_id: int):
    """Get messages for a specific conversation."""
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return db.get_chat_history(conv_id)


# --- Chat (conversation-scoped) ---

SYSTEM_PROMPT = """You are KaziAI, an intelligent AI career assistant. You help job seekers with:
- Searching and finding relevant jobs
- Analyzing job descriptions against resumes
- ATS (Applicant Tracking System) resume optimization
- Writing tailored cover letters
- Interview preparation and coaching
- Career advice and strategy

You have access to tools that can search real job boards, score resumes, and generate materials.
Be conversational, helpful, and proactive. Give specific, actionable advice.
When a user asks to search for jobs, extract the key skills/role from their message.
Keep responses concise but insightful. Use markdown formatting for readability."""


def _get_llm_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")


def _truncate_title(text: str, max_len: int = 40) -> str:
    """Truncate text to max_len at a word boundary."""
    text = text.strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > 10:
        truncated = truncated[:last_space]
    return truncated + "..."


def _run_tool_action(msg: str) -> str | None:
    """Check if the message needs a tool action and return tool results."""
    lower = msg.lower()

    if any(w in lower for w in ["search", "find", "look for", "jobs", "hiring", "openings", "vacancies"]):
        words = msg.split()
        stop_words = {"search", "find", "look", "jobs", "for", "with", "that", "have",
                      "me", "some", "the", "and", "need", "want", "please", "can", "you",
                      "asap", "now", "urgently", "remote", "job", "a", "i", "any"}
        keywords = [w for w in words if len(w) > 2 and w.lower() not in stop_words]
        if not keywords:
            keywords = ["software", "engineer"]

        tool = JobSearchTool()
        result = tool.execute(keywords=keywords, max_results=5)
        jobs = result.get("jobs", [])

        if jobs:
            tool_data = f"[SEARCH RESULTS: Found {result['total_found']} jobs]\n"
            for i, job in enumerate(jobs, 1):
                tool_data += (
                    f"{i}. {job['title']} at {job['company']} "
                    f"({job['location']}) - {job.get('url', 'No URL')}\n"
                )
            return tool_data
        return "[SEARCH RESULTS: No jobs found for those keywords]"

    return None


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Handle a chat message using LLM with tool augmentation."""
    conversation_id = req.conversation_id

    # Auto-create conversation if none provided
    if conversation_id is None:
        title = _truncate_title(req.message)
        conversation_id = db.create_conversation(title)

    db.save_chat_message("user", req.message, conversation_id)

    # Get recent chat history for context
    history = db.get_chat_history(conversation_id, limit=20)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[:-1]:  # exclude current message (already in history)
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Check if we need to run a tool and inject results
    tool_result = _run_tool_action(req.message)
    if tool_result:
        messages.append({
            "role": "user",
            "content": f"{req.message}\n\n{tool_result}\n\nUse these results to give a helpful response.",
        })
    else:
        messages.append({"role": "user", "content": req.message})

    # Try LLM response
    client = _get_llm_client()
    if client:
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
            )
            response = completion.choices[0].message.content
        except Exception as e:
            response = f"I'm having trouble connecting to my AI backend: {str(e)[:100]}. Try again in a moment."
    else:
        response = "AI backend not configured. Please set GROQ_API_KEY in your .env file."

    db.save_chat_message("assistant", response, conversation_id)
    return {"response": response, "conversation_id": conversation_id}


# Serve React frontend for all non-API routes
@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    """Serve the React SPA for all non-API routes."""
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "KaziAI API is running. Frontend not built yet."}
