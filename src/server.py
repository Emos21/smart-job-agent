import os
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

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


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Handle a chat message from the dashboard."""
    db.save_chat_message("user", req.message)

    # Simple intent detection — route to the right action
    msg = req.message.lower()

    if any(w in msg for w in ["search", "find", "look for", "jobs"]):
        # Extract keywords from the message
        words = req.message.split()
        keywords = [w for w in words if len(w) > 3 and w.lower() not in
                    ["search", "find", "look", "jobs", "for", "with", "that", "have"]]
        if not keywords:
            keywords = ["python", "backend"]

        tool = JobSearchTool()
        result = tool.execute(keywords=keywords, max_results=5)
        jobs = result.get("jobs", [])

        if jobs:
            response = f"Found {result['total_found']} jobs. Here are the top {len(jobs)}:\n\n"
            for i, job in enumerate(jobs, 1):
                response += f"{i}. **{job['title']}** at {job['company']} ({job['location']})\n"
            response += "\nWant me to analyze any of these against your resume?"
        else:
            response = "No jobs found matching those keywords. Try different terms."

    elif any(w in msg for w in ["analyze", "match", "score", "ats"]):
        response = (
            "To analyze a job, paste the job description text and I'll run "
            "the full analysis pipeline — ATS scoring, skills matching, "
            "and interview prep."
        )

    elif any(w in msg for w in ["interview", "prep", "questions"]):
        response = (
            "I can generate interview questions for any role. "
            "Tell me the role title and company, and I'll prep you."
        )

    elif any(w in msg for w in ["hello", "hi", "hey"]):
        response = (
            "Hey! I'm KaziAI, your career assistant. I can:\n\n"
            "- **Search** for jobs matching your skills\n"
            "- **Analyze** job descriptions against your resume\n"
            "- **Score** your resume for ATS compatibility\n"
            "- **Write** tailored cover letters\n"
            "- **Prep** you for interviews\n\n"
            "What would you like to do?"
        )

    else:
        response = (
            "I can help you with:\n"
            "- **Search jobs** — 'find python backend jobs'\n"
            "- **Analyze a role** — paste a job description\n"
            "- **Interview prep** — 'prep me for [role] at [company]'\n\n"
            "What would you like to do?"
        )

    db.save_chat_message("assistant", response)
    return {"response": response}


@app.get("/api/chat/history")
def chat_history():
    """Get chat history."""
    return db.get_chat_history()


# Serve React frontend for all non-API routes
@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    """Serve the React SPA for all non-API routes."""
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "KaziAI API is running. Frontend not built yet."}
