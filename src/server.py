import os
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from . import database as db
from .auth import hash_password, verify_password, create_token, get_current_user, verify_google_token
from .tools.base import ToolRegistry
from .tools.job_search import JobSearchTool
from .tools.jd_parser import JDParserTool
from .tools.resume_analyzer import ResumeAnalyzerTool
from .tools.skills_matcher import SkillsMatcherTool
from .tools.ats_scorer import ATSScorerTool
from .tools.interview_prep import InterviewPrepTool
from .tools.cover_letter import CoverLetterTool
from .tools.resume_rewriter import ResumeRewriterTool
from .tools.company_researcher import CompanyResearcherTool
from .tools.github_analyzer import GitHubAnalyzerTool
from .tools.salary_research import SalaryResearchTool
from .tools.email_drafter import EmailDrafterTool
from .tools.learning_path import LearningPathTool
from .tools.mock_interview import MockInterviewTool
from .tools.web_fetch import WebFetchTool
from .agents.orchestrator import Orchestrator
from .agents.router import AgentRouter, RoutingDecision
from .agents.planner import GoalPlanner
from .episodic_memory import EpisodicMemory
from .websocket_manager import ws_manager, authenticate_ws

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    # Start background scheduler for proactive notifications
    from .background import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="KaziAI",
    description="AI-powered career platform with multi-agent orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a clean JSON error."""
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )

# Serve React frontend static files
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")


@app.get("/api/health")
def health_check():
    """Health check endpoint for monitoring and load balancers."""
    provider = os.getenv("LLM_PROVIDER", "groq")
    client = _get_llm_client()
    return {
        "status": "healthy",
        "llm_provider": provider,
        "llm_model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        "llm_connected": client is not None,
    }


@app.get("/api/version")
def version_info():
    """Return API version and available features."""
    return {
        "version": "1.0.0",
        "features": {
            "multi_agent": True,
            "websocket_push": True,
            "rl_optimization": True,
            "goal_planning": True,
            "agent_negotiation": True,
            "episodic_memory": True,
            "background_tasks": True,
        },
    }


# --- Request/Response Models ---

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str


class SearchRequest(BaseModel):
    keywords: list[str]
    max_results: int = 10


class AnalyzeRequest(BaseModel):
    jd_text: str
    resume_text: str = ""
    resume_path: str = ""


class PipelineRequest(BaseModel):
    jd_text: str
    resume_text: str = ""
    resume_path: str = ""
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
    file_content: str | None = None
    file_name: str | None = None


class RenameConversationRequest(BaseModel):
    title: str


class ProfileRequest(BaseModel):
    target_role: str = ""
    experience_level: str = ""
    skills: list[str] = []
    bio: str = ""
    linkedin_url: str = ""
    github_username: str = ""
    location: str = ""


class SaveResumeRequest(BaseModel):
    name: str
    content: str
    is_default: bool = False


class CreateGoalRequest(BaseModel):
    goal_text: str


class FeedbackRequest(BaseModel):
    rating: str  # "positive" or "negative"


# --- Auth Routes ---

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    """Register a new user."""
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = db.get_user_by_email(req.email.lower().strip())
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    password_hash = hash_password(req.password)
    user_id = db.create_user(req.email.lower().strip(), password_hash, req.name.strip())
    user = db.get_user_by_id(user_id)
    token = create_token(user_id)

    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"]},
    }


@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Log in an existing user."""
    user = db.get_user_by_email(req.email.lower().strip())
    if not user or not user["password_hash"] or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user["id"])
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"]},
    }


@app.post("/api/auth/google")
def google_auth(req: GoogleAuthRequest):
    """Authenticate with a Google ID token."""
    info = verify_google_token(req.credential)
    email = info["email"].lower().strip()
    name = info["name"]
    google_id = info["google_id"]

    # Check if user exists by google_id
    user = db.get_user_by_google_id(google_id)
    if not user:
        # Check if user exists by email (link Google to existing account)
        user = db.get_user_by_email(email)
        if user:
            db.link_google_id(user["id"], google_id)
        else:
            # Create new user (no password)
            user_id = db.create_user(email, None, name, google_id=google_id)
            user = db.get_user_by_id(user_id)

    token = create_token(user["id"])
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"]},
    }


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


# --- API Routes ---

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "KaziAI"}


@app.post("/api/search")
def search_jobs(req: SearchRequest, user: dict = Depends(get_current_user)):
    """Search for jobs across multiple boards."""
    tool = JobSearchTool()
    result = tool.execute(keywords=req.keywords, max_results=req.max_results)
    return result


@app.post("/api/analyze")
def analyze_job(req: AnalyzeRequest, user: dict = Depends(get_current_user)):
    """Analyze a JD against a resume using the Match agent pipeline."""
    # Parse JD
    jd_tool = JDParserTool()
    jd_result = jd_tool.execute(source=req.jd_text)

    # Get resume text — either directly provided or from file
    resume_text = req.resume_text.strip()
    resume_result = {}
    if resume_text:
        # Resume text provided directly (from frontend paste/upload)
        resume_result = {
            "success": True,
            "raw_text": resume_text,
            "sections": {"full_resume": resume_text},
        }
    elif req.resume_path:
        resume_tool = ResumeAnalyzerTool()
        resume_result = resume_tool.execute(file_path=req.resume_path)
        if not resume_result.get("success"):
            raise HTTPException(status_code=400, detail=resume_result.get("error"))
        resume_text = resume_result.get("raw_text", "")
    else:
        raise HTTPException(status_code=400, detail="Please provide resume text or a resume file path")

    # ATS Score
    jd_keywords = []
    for section in jd_result.get("sections", {}).values():
        words = section.split()
        jd_keywords.extend([w.strip(",-.:;") for w in words if len(w) > 3])
    jd_keywords = list(set(jd_keywords))[:30]

    ats_tool = ATSScorerTool()
    ats_result = ats_tool.execute(
        resume_text=resume_text,
        jd_keywords=jd_keywords,
    )

    return {
        "jd_analysis": jd_result,
        "resume_analysis": resume_result,
        "ats_score": ats_result,
    }


@app.post("/api/pipeline")
def run_pipeline(req: PipelineRequest, user: dict = Depends(get_current_user)):
    """Run the full multi-agent pipeline (Match -> Forge -> Coach)."""
    # Get resume text — either directly provided or from file
    resume_text = req.resume_text.strip()
    if not resume_text and req.resume_path:
        resume_tool = ResumeAnalyzerTool()
        resume_result = resume_tool.execute(file_path=req.resume_path)
        if not resume_result.get("success"):
            raise HTTPException(status_code=400, detail=resume_result.get("error"))
        resume_text = resume_result.get("raw_text", "")

    if not resume_text:
        raise HTTPException(status_code=400, detail="Please provide resume text or a resume file path")

    orchestrator = Orchestrator(provider=os.getenv("LLM_PROVIDER", "groq"))
    result = orchestrator.full_pipeline(
        jd_text=req.jd_text,
        resume_path=req.resume_path or "user_provided",
        resume_text=resume_text,
        role=req.role,
        company=req.company,
    )

    return {
        "analysis": result["analysis"],
        "materials": result["materials"],
        "interview_prep": result["interview_prep"],
    }


@app.post("/api/jobs/save")
def save_job(req: SaveJobRequest, user: dict = Depends(get_current_user)):
    """Save a job to the tracker."""
    job_id = db.save_job(req.model_dump(), user_id=user["id"])
    return {"id": job_id, "message": "Job saved"}


@app.get("/api/jobs")
def list_jobs(user: dict = Depends(get_current_user)):
    """Get saved jobs for the current user."""
    return db.get_jobs(user_id=user["id"])


@app.post("/api/applications/{job_id}")
def create_application(job_id: int, jd_text: str = "", user: dict = Depends(get_current_user)):
    """Create an application for a saved job."""
    app_id = db.create_application(job_id, jd_text, user_id=user["id"])
    return {"id": app_id, "message": "Application created"}


@app.get("/api/applications")
def list_applications(status: str | None = None, user: dict = Depends(get_current_user)):
    """Get applications for the current user, optionally filtered by status."""
    return db.get_applications(user_id=user["id"], status=status)


@app.patch("/api/applications/{app_id}")
def update_application(app_id: int, req: UpdateApplicationRequest, user: dict = Depends(get_current_user)):
    """Update an application's status or notes."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    db.update_application(app_id, user_id=user["id"], **updates)
    return {"message": "Updated"}


# --- Dashboard ---

@app.get("/api/dashboard")
def get_dashboard(user: dict = Depends(get_current_user)):
    """Aggregated stats for the user's dashboard."""
    jobs = db.get_jobs(user_id=user["id"])
    applications = db.get_applications(user_id=user["id"])
    conversations = db.get_conversations(user_id=user["id"])
    resumes = db.get_resumes(user["id"])
    profile = db.get_profile(user["id"])

    status_counts = {}
    for app in applications:
        s = app.get("status", "saved")
        status_counts[s] = status_counts.get(s, 0) + 1

    recent_apps = applications[:5]

    return {
        "total_jobs_saved": len(jobs),
        "total_applications": len(applications),
        "total_conversations": len(conversations),
        "total_resumes": len(resumes),
        "has_profile": profile is not None,
        "application_status": status_counts,
        "recent_applications": [
            {"title": a.get("title", ""), "company": a.get("company", ""), "status": a.get("status", ""), "updated_at": a.get("updated_at", "")}
            for a in recent_apps
        ],
    }


# --- Learning Path ---

@app.post("/api/learning-path")
def generate_learning_path(user: dict = Depends(get_current_user)):
    """Generate a learning path based on the user's profile skill gaps."""
    from .tools.learning_path import LearningPathTool

    profile = db.get_profile(user["id"])
    if not profile or not profile.get("skills"):
        raise HTTPException(status_code=400, detail="Set your skills in your profile first")

    target_role = profile.get("target_role", "Software Engineer")
    current_skills = profile.get("skills", [])

    # Suggest common skills for the target role that the user doesn't have
    role_skills_map = {
        "frontend": ["React", "TypeScript", "CSS", "Testing", "Performance", "Accessibility"],
        "backend": ["Python", "SQL", "Docker", "REST APIs", "System Design", "Testing"],
        "fullstack": ["React", "Node.js", "TypeScript", "SQL", "Docker", "System Design"],
        "data": ["Python", "SQL", "Machine Learning", "Statistics", "Docker", "Cloud"],
        "devops": ["Docker", "Kubernetes", "AWS", "CI/CD", "Terraform", "Linux"],
    }

    # Try to match role to suggestions
    role_lower = target_role.lower()
    suggested = []
    for key, skills in role_skills_map.items():
        if key in role_lower:
            suggested = skills
            break
    if not suggested:
        suggested = ["Python", "SQL", "Docker", "System Design", "TypeScript", "React"]

    current_lower = [s.lower() for s in current_skills]
    missing = [s for s in suggested if s.lower() not in current_lower]

    if not missing:
        return {"success": True, "message": "Your skills look solid for this role!", "learning_paths": [], "total_estimated_hours": 0, "total_estimated_weeks": 0}

    tool = LearningPathTool()
    return tool.execute(
        missing_skills=missing[:6],
        current_skills=current_skills,
        target_role=target_role,
    )


# --- Profile & Resume endpoints ---

@app.get("/api/profile")
def get_profile(user: dict = Depends(get_current_user)):
    """Get the current user's profile."""
    profile = db.get_profile(user["id"])
    if not profile:
        return {"user_id": user["id"], "target_role": "", "experience_level": "", "skills": [], "bio": "", "linkedin_url": "", "github_username": "", "location": ""}
    return profile


@app.put("/api/profile")
def update_profile(req: ProfileRequest, user: dict = Depends(get_current_user)):
    """Create or update the current user's profile."""
    profile = db.upsert_profile(
        user["id"],
        target_role=req.target_role,
        experience_level=req.experience_level,
        skills=req.skills,
        bio=req.bio,
        linkedin_url=req.linkedin_url,
        github_username=req.github_username,
        location=req.location,
    )
    return profile


@app.get("/api/resumes")
def list_resumes(user: dict = Depends(get_current_user)):
    """List all saved resumes for the current user."""
    return db.get_resumes(user["id"])


@app.post("/api/resumes")
def save_resume(req: SaveResumeRequest, user: dict = Depends(get_current_user)):
    """Save a new resume."""
    resume_id = db.save_resume(user["id"], req.name, req.content, req.is_default)
    return {"id": resume_id, "message": "Resume saved"}


@app.delete("/api/resumes/{resume_id}")
def delete_resume(resume_id: int, user: dict = Depends(get_current_user)):
    """Delete a saved resume."""
    deleted = db.delete_resume(resume_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"message": "Resume deleted"}


@app.patch("/api/resumes/{resume_id}/default")
def set_default_resume(resume_id: int, user: dict = Depends(get_current_user)):
    """Set a resume as the default."""
    updated = db.set_default_resume(resume_id, user["id"])
    if not updated:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"message": "Default resume updated"}


# --- Conversation endpoints ---

@app.get("/api/conversations")
def list_conversations(user: dict = Depends(get_current_user)):
    """Get all conversations for the current user, most recent first."""
    return db.get_conversations(user_id=user["id"])


@app.post("/api/conversations")
def create_conversation_endpoint(user: dict = Depends(get_current_user)):
    """Create a new empty conversation."""
    conv_id = db.create_conversation("New Chat", user_id=user["id"])
    conv = db.get_conversation(conv_id)
    return conv


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int, user: dict = Depends(get_current_user)):
    """Delete a conversation and all its messages."""
    conv = db.get_conversation_for_user(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete_conversation(conv_id)
    return {"message": "Conversation deleted"}


@app.patch("/api/conversations/{conv_id}")
def rename_conversation(conv_id: int, req: RenameConversationRequest, user: dict = Depends(get_current_user)):
    """Rename a conversation."""
    conv = db.get_conversation_for_user(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.update_conversation_title(conv_id, req.title)
    return {"message": "Conversation renamed"}


@app.get("/api/conversations/{conv_id}/messages")
def get_conversation_messages(conv_id: int, user: dict = Depends(get_current_user)):
    """Get messages for a specific conversation."""
    conv = db.get_conversation_for_user(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return db.get_chat_history(conv_id)


# --- File extraction ---

@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Extract text from an uploaded file (.txt, .md, .pdf)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    content = await file.read()

    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(stream=content, filetype="pdf")
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
        except ImportError:
            raise HTTPException(status_code=500, detail="PDF support not installed (pymupdf)")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    elif ext in (".txt", ".md", ".text"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    return {"text": text, "filename": file.filename, "char_count": len(text)}


# --- Chat (conversation-scoped, agentic with function calling) ---

SYSTEM_PROMPT = """You are Kazi, a sharp and friendly career AI assistant. You talk like a smart friend who happens to have powerful job search and career tools at your fingertips.

PERSONALITY:
- Conversational and warm — not corporate or robotic
- Concise — say what matters, skip the filler. Short paragraphs, not walls of text
- Confident — you know your stuff, don't hedge everything with disclaimers
- When someone says "hi" or greets you, just be friendly and brief. Don't list your capabilities
- Ask smart follow-up questions to understand what people actually need

CRITICAL RULES:
- NEVER mention tool names, function names, or internal system details to the user. No "<function=...>", no "I used the search_jobs tool", no "calling the parse_job_description function"
- Just present results naturally. Say "I found 8 Python developer jobs" not "I used the search_jobs tool and found 8 results"
- NEVER start responses with "I've provided..." or "Based on the functions available..."
- Keep responses under 200 words unless the user asks for detailed analysis
- Use markdown formatting but keep it clean — bullet points for lists, bold for emphasis, not everything at once
- When showing job results, format them as a clean readable list with the key info (title, company, location, salary if available)
- When you don't know something, say so honestly instead of giving vague answers

WHEN TO USE TOOLS:
- User wants to find jobs → search with specific keywords from their message
- User shares a job description → analyze it
- User wants resume feedback → use ATS scoring
- User wants interview help → generate targeted questions
- User asks about salary → research market rates
- User shares a URL → fetch and read it
- If the user is just chatting or asking general questions, just talk — don't force a tool call

DOCUMENT HANDLING:
- When file content is attached between --- markers, analyze it thoroughly
- If it's a resume/CV, give career-relevant feedback on structure, content, ATS readiness, and areas for improvement
- If it's a job description, analyze requirements, qualifications, and company expectations
- If it's another document type, summarize and help the user with whatever they need"""


# Build a chat tool registry with all tools
def _build_chat_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(JobSearchTool())
    registry.register(JDParserTool())
    registry.register(SkillsMatcherTool())
    registry.register(ATSScorerTool())
    registry.register(InterviewPrepTool())
    registry.register(CoverLetterTool())
    registry.register(ResumeRewriterTool())
    registry.register(CompanyResearcherTool())
    registry.register(GitHubAnalyzerTool())
    registry.register(SalaryResearchTool())
    registry.register(EmailDrafterTool())
    registry.register(LearningPathTool())
    registry.register(MockInterviewTool())
    registry.register(ResumeAnalyzerTool())
    registry.register(WebFetchTool())
    return registry

CHAT_REGISTRY = _build_chat_registry()
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "6"))

# Agent router for smart dispatch
_agent_router = AgentRouter()

# Active dispatch tracking for cancellation (Phase 6)
_active_dispatches: dict[int, dict] = {}  # conversation_id -> {"cancel_requested": False}

# Friendly agent names for status messages
_AGENT_STATUS = {
    "scout": "Scout Agent searching for jobs",
    "match": "Match Agent analyzing compatibility",
    "forge": "Forge Agent writing materials",
    "coach": "Coach Agent preparing interview prep",
}

# Simple TTL cache for tool results (5-minute expiry)
_tool_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300  # seconds
_CACHEABLE_TOOLS = {"search_jobs", "research_company", "analyze_github", "research_salary", "fetch_url"}


def _get_llm_client():
    provider = os.getenv("LLM_PROVIDER", "groq")
    if provider == "ollama":
        return OpenAI(
            api_key="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )
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


def _execute_tool_call(name: str, arguments: dict) -> dict:
    """Execute a tool by name and return its result, with caching for eligible tools."""
    import time

    tool = CHAT_REGISTRY.get(name)
    if tool is None:
        return {"success": False, "error": f"Unknown tool: {name}"}

    # Check cache for cacheable tools
    if name in _CACHEABLE_TOOLS:
        cache_key = f"{name}:{json.dumps(arguments, sort_keys=True)}"
        cached = _tool_cache.get(cache_key)
        if cached:
            ts, result = cached
            if time.time() - ts < _CACHE_TTL:
                return result

    try:
        result = tool.execute(**arguments)
    except Exception as e:
        return {"success": False, "error": f"Tool failed: {str(e)}"}

    # Store in cache
    if name in _CACHEABLE_TOOLS:
        cache_key = f"{name}:{json.dumps(arguments, sort_keys=True)}"
        _tool_cache[cache_key] = (time.time(), result)
        # Evict old entries (keep cache bounded)
        if len(_tool_cache) > 100:
            oldest_key = min(_tool_cache, key=lambda k: _tool_cache[k][0])
            del _tool_cache[oldest_key]

    return result


def _clean_response(text: str) -> str:
    """Strip any leaked function call syntax from LLM responses."""
    import re
    # Remove <function=name> or </function> tags
    text = re.sub(r'</?function[^>]*>', '', text)
    # Remove {\"name\": \"tool_name\"...} JSON tool references
    text = re.sub(r'\{"name":\s*"[a-z_]+"[^}]*\}', '', text)
    # Clean up any double whitespace left behind
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


@app.post("/api/chat")
def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    """Handle a chat message using LLM with agentic function calling.

    The LLM autonomously decides when to call tools (job search, ATS scoring,
    interview prep, etc.) based on the user's message. This is the ReAct pattern:
    Reason -> Act (call tool) -> Observe (read result) -> Respond.
    """
    conversation_id = req.conversation_id

    # Auto-create conversation if none provided
    if conversation_id is None:
        title = _truncate_title(req.message)
        conversation_id = db.create_conversation(title, user_id=user["id"])
    else:
        # Verify ownership
        conv = db.get_conversation_for_user(conversation_id, user["id"])
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    db.save_chat_message("user", req.message, conversation_id)

    # Build system prompt with user context
    profile = db.get_profile(user["id"])
    default_resume = db.get_default_resume(user["id"])
    system_content = SYSTEM_PROMPT + _build_user_context(user, profile, default_resume)

    # Build conversation messages from history
    history = db.get_chat_history(conversation_id, limit=20)
    messages = [{"role": "system", "content": system_content}]
    for msg in history[:-1]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Build the user message, injecting file content if attached
    user_content = req.message
    if req.file_content:
        file_label = req.file_name or "attached file"
        truncated = req.file_content[:6000]
        user_content = f"{req.message}\n\n[Attached file: {file_label}]\n---\n{truncated}\n---"
    messages.append({"role": "user", "content": user_content})

    client = _get_llm_client()
    if not client:
        response = "AI backend not configured. Set LLM_PROVIDER=ollama for local inference or GROQ_API_KEY for cloud."
        db.save_chat_message("assistant", response, conversation_id)
        return {"response": response, "conversation_id": conversation_id}

    # Agentic loop: let the LLM call tools, feed results back, repeat
    tool_specs = CHAT_REGISTRY.to_openai_specs()
    response = ""

    try:
        for _round in range(MAX_TOOL_ROUNDS + 1):
            completion = client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=messages,
                tools=tool_specs if _round < MAX_TOOL_ROUNDS else None,
                tool_choice="auto" if _round < MAX_TOOL_ROUNDS else None,
                max_tokens=1024,
                temperature=0.6,
            )

            message = completion.choices[0].message

            # If the LLM wants to call tools, execute them and loop
            if message.tool_calls:
                # Add the assistant's tool call message
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                })

                # Execute each tool call and add results
                for tc in message.tool_calls:
                    func_name = tc.function.name
                    try:
                        func_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        func_args = {}

                    result = _execute_tool_call(func_name, func_args)
                    # Truncate large results to avoid context overflow
                    result_str = json.dumps(result, indent=2)
                    if len(result_str) > 4000:
                        result_str = result_str[:4000] + "\n... (truncated)"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })
                continue  # Loop back to let LLM process tool results

            # No tool calls — this is the final response
            response = message.content or "I processed your request but couldn't generate a response."
            break

    except Exception as e:
        response = f"Something went wrong — {str(e)[:200]}. Mind trying again?"

    # Strip any leaked function call syntax from the response
    response = _clean_response(response)
    db.save_chat_message("assistant", response, conversation_id)
    return {"response": response, "conversation_id": conversation_id}


# Friendly tool names for status messages
_TOOL_STATUS = {
    "search_jobs": "Searching for jobs",
    "parse_job_description": "Analyzing job description",
    "analyze_resume": "Analyzing resume",
    "match_skills": "Matching skills",
    "score_ats": "Scoring ATS compatibility",
    "prepare_interview": "Preparing interview questions",
    "generate_cover_letter": "Writing cover letter",
    "rewrite_resume": "Rewriting resume",
    "research_company": "Researching company",
    "analyze_github": "Analyzing GitHub profile",
    "research_salary": "Researching salary data",
    "draft_email": "Drafting email",
    "generate_learning_path": "Creating learning path",
    "mock_interview": "Running mock interview",
    "fetch_url": "Reading webpage",
}


def _build_user_context(user: dict, profile: dict | None, default_resume: dict | None, memories_text: str = "") -> str:
    """Build user context string for system prompt injection."""
    parts = []
    if user.get("name"):
        parts.append(f"Name: {user['name']}")
    if profile:
        if profile.get("target_role"):
            parts.append(f"Targeting: {profile['target_role']} roles")
        if profile.get("experience_level"):
            parts.append(f"Experience: {profile['experience_level']}")
        if profile.get("skills"):
            skills_str = ", ".join(profile["skills"][:15])
            parts.append(f"Skills: {skills_str}")
        if profile.get("location"):
            parts.append(f"Location: {profile['location']}")
    if default_resume:
        resume_preview = default_resume["content"][:2000]
        parts.append(f"\nResume on file ({default_resume['name']}):\n{resume_preview}")
    result = ""
    if parts:
        result = "\n\nUSER CONTEXT:\n" + "\n".join(parts)
    if memories_text:
        result += f"\n\n{memories_text}"
    return result


def _generate_direct_llm(client, messages, tool_specs):
    """Generator for direct LLM path with tool calling (general chat)."""
    full_response = ""

    for _round in range(MAX_TOOL_ROUNDS + 1):
        is_last_round = _round >= MAX_TOOL_ROUNDS

        completion = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            messages=messages,
            tools=tool_specs if not is_last_round else None,
            tool_choice="auto" if not is_last_round else None,
            max_tokens=1024,
            temperature=0.6,
            stream=False,
        )

        message = completion.choices[0].message

        if message.tool_calls:
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            })

            for tc in message.tool_calls:
                func_name = tc.function.name
                status = _TOOL_STATUS.get(func_name, f"Using {func_name}")
                yield ("tool_status", {"tool": func_name, "status": status})

                try:
                    func_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    func_args = {}

                result = _execute_tool_call(func_name, func_args)
                result_str = json.dumps(result, indent=2)
                if len(result_str) > 4000:
                    result_str = result_str[:4000] + "\n... (truncated)"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })
            continue

        # Final response — stream it
        stream = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            messages=messages,
            max_tokens=1024,
            temperature=0.6,
            stream=True,
        )
        full_response = ""
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                full_response += delta.content
                yield ("content", {"text": delta.content})
        break

    yield ("_final", full_response)


def _generate_agent_dispatch(client, messages, routing, user_message, resume_text, profile, user_id=None, conversation_id=None, cancel_check=None):
    """Generator for agent-dispatched path. Uses orchestrator with message bus, evaluator, and structured communication."""
    orchestrator = Orchestrator(provider=os.getenv("LLM_PROVIDER", "groq"))

    # Collect events from orchestrator callbacks
    events = []

    def on_status(agent_name, status):
        friendly = _AGENT_STATUS.get(agent_name, f"Running {agent_name} agent")
        msg = friendly if status == "running" else f"{agent_name.capitalize()} {'done' if status == 'complete' else 'failed'}"
        events.append(("agent_status", {"agent": agent_name, "status": status, "message": msg}))

    def on_thought(agent_name, thought, tool_name):
        events.append(("agent_reasoning", {"agent": agent_name, "thought": thought[:300], "tool": tool_name}))

    def on_evaluator(decision):
        events.append(("evaluator", decision))

    # Dispatch with structured communication
    results = orchestrator.dispatch(
        routing=routing,
        user_message=user_message,
        resume_text=resume_text,
        profile=profile,
        on_agent_status=on_status,
        user_id=user_id,
        conversation_id=conversation_id,
        cancel_check=cancel_check,
        on_agent_thought=on_thought,
        on_evaluator=on_evaluator,
    )

    # Yield all collected events
    for evt in events:
        yield evt

    # Emit trace IDs for feedback UI
    trace_ids = [r.trace_id for r in results if r.trace_id is not None]
    if trace_ids:
        yield ("trace_ids", {"ids": trace_ids})

    # Check if cancelled
    if cancel_check and cancel_check():
        partial = "\n".join(r.output[:500] for r in results if r.success)
        yield ("content", {"text": f"Stopped early. Here's what I found so far:\n\n{partial}"})
        yield ("_final", partial)
        return

    # Build synthesis prompt with agent outputs
    agent_context = ""
    for r in results:
        if r.success:
            output_preview = r.output[:3000]
            agent_context += f"\n\n[{r.agent_name.upper()} AGENT RESULTS]\n{output_preview}\n"

    if agent_context:
        messages.append({
            "role": "system",
            "content": (
                "AGENT ANALYSIS RESULTS (synthesize these into your response — "
                "do NOT mention agent names to the user):"
                f"{agent_context}"
            ),
        })

    # Stream the final synthesized response
    stream = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        messages=messages,
        max_tokens=2048,
        temperature=0.6,
        stream=True,
    )
    full_response = ""
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            full_response += delta.content
            yield ("content", {"text": delta.content})

    yield ("_final", full_response)


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest, user: dict = Depends(get_current_user)):
    """Streaming chat endpoint using Server-Sent Events.

    Flow:
    1. Classify intent via AgentRouter
    2. If general_chat: direct LLM path with tool calling
    3. If specific agents: dispatch via orchestrator, then synthesize
    """
    conversation_id = req.conversation_id

    if conversation_id is None:
        title = _truncate_title(req.message)
        conversation_id = db.create_conversation(title, user_id=user["id"])
    else:
        conv = db.get_conversation_for_user(conversation_id, user["id"])
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    db.save_chat_message("user", req.message, conversation_id)

    # Gather user context
    profile = db.get_profile(user["id"])
    default_resume = db.get_default_resume(user["id"])

    # Retrieve episodic memories
    memory = EpisodicMemory(user["id"])
    memories_text = memory.recall_as_context(limit=10)

    # Build system prompt
    system_content = SYSTEM_PROMPT + _build_user_context(user, profile, default_resume, memories_text)

    # Build conversation messages
    history = db.get_chat_history(conversation_id, limit=20)
    messages = [{"role": "system", "content": system_content}]
    for msg in history[:-1]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    user_content = req.message
    if req.file_content:
        file_label = req.file_name or "attached file"
        truncated = req.file_content[:6000]
        user_content = f"{req.message}\n\n[Attached file: {file_label}]\n---\n{truncated}\n---"
    messages.append({"role": "user", "content": user_content})

    client = _get_llm_client()

    # Route the message
    routing = _agent_router.route(
        req.message,
        has_resume=default_resume is not None,
        has_profile=profile is not None,
    )

    resume_text = default_resume["content"] if default_resume else ""

    def generate():
        nonlocal conversation_id
        if not client:
            yield f"data: {json.dumps({'type': 'content', 'text': 'AI backend not configured. Set LLM_PROVIDER=ollama for local inference or GROQ_API_KEY for cloud.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id})}\n\n"
            return

        # Register for cancellation
        _active_dispatches[conversation_id] = {"cancel_requested": False}

        def dispatch_cancel_check():
            state = _active_dispatches.get(conversation_id, {})
            return state.get("cancel_requested", False)

        yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conversation_id})}\n\n"

        # Emit routing decision to frontend
        yield f"data: {json.dumps({'type': 'routing', 'intent': routing.intent, 'agents': routing.agents})}\n\n"

        full_response = ""

        try:
            gen = None
            multi_step_prefix_events = []

            if routing.intent == "general_chat" or not routing.agents:
                # Direct LLM path with tool calling
                gen = _generate_direct_llm(client, messages, CHAT_REGISTRY.to_openai_specs())
            elif routing.intent == "multi_step":
                # Create a goal plan and execute the first step
                try:
                    plan = _goal_planner.create_plan(req.message, _build_user_context(user, profile, default_resume, ""))
                    goal_id = _goal_planner.save_plan(user["id"], plan)
                    plan_title = plan["title"]
                    plan_step_count = len(plan["steps"])
                    status_data = json.dumps({
                        "type": "agent_status",
                        "agent": "planner",
                        "status": "complete",
                        "message": f"Created plan: {plan_title} ({plan_step_count} steps)",
                    })
                    multi_step_prefix_events.append(f"data: {status_data}\n\n")

                    first_step = plan["steps"][0] if plan["steps"] else None
                    if first_step:
                        first_routing = RoutingDecision(
                            intent="goal_step",
                            agents=[first_step["agent_name"]],
                            extracted_context=routing.extracted_context,
                            reasoning="Executing first step of goal plan",
                        )
                        # Add plan context to messages for synthesis
                        plan_text = f"\n\nI created a goal plan: '{plan['title']}' with {len(plan['steps'])} steps:\n"
                        for i, s in enumerate(plan["steps"], 1):
                            plan_text += f"{i}. {s['title']} ({s['agent_name']} agent)\n"
                        plan_text += f"\nThe user can say 'continue my plan' or check the Goals tab to resume."
                        messages.append({"role": "system", "content": plan_text})

                        gen = _generate_agent_dispatch(
                            client, messages, first_routing, req.message, resume_text, profile,
                            user_id=user["id"], conversation_id=conversation_id,
                            cancel_check=dispatch_cancel_check,
                        )
                    else:
                        gen = _generate_direct_llm(client, messages, CHAT_REGISTRY.to_openai_specs())
                except Exception:
                    gen = _generate_agent_dispatch(
                        client, messages, routing, req.message, resume_text, profile,
                        user_id=user["id"], conversation_id=conversation_id,
                        cancel_check=dispatch_cancel_check,
                    )
            else:
                # Agent dispatch path
                gen = _generate_agent_dispatch(
                    client, messages, routing, req.message, resume_text, profile,
                    user_id=user["id"], conversation_id=conversation_id,
                    cancel_check=dispatch_cancel_check,
                )

            # Emit any prefix events from multi-step planning
            for evt in multi_step_prefix_events:
                yield evt

            for event_type, event_data in gen:
                if event_type == "_final":
                    full_response = event_data
                elif event_type == "tool_status":
                    yield f"data: {json.dumps({'type': 'tool_status', **event_data})}\n\n"
                elif event_type == "agent_status":
                    yield f"data: {json.dumps({'type': 'agent_status', **event_data})}\n\n"
                elif event_type == "evaluator":
                    yield f"data: {json.dumps({'type': 'evaluator', **event_data})}\n\n"
                elif event_type == "agent_reasoning":
                    yield f"data: {json.dumps({'type': 'agent_reasoning', **event_data})}\n\n"
                elif event_type == "trace_ids":
                    yield f"data: {json.dumps({'type': 'trace_ids', **event_data})}\n\n"
                elif event_type == "negotiation_round":
                    yield f"data: {json.dumps({'type': 'negotiation_round', **event_data})}\n\n"
                elif event_type == "negotiation_result":
                    yield f"data: {json.dumps({'type': 'negotiation_result', **event_data})}\n\n"
                elif event_type == "content":
                    yield f"data: {json.dumps({'type': 'content', **event_data})}\n\n"

        except Exception as e:
            full_response = f"Something went wrong — {str(e)[:200]}. Mind trying again?"
            yield f"data: {json.dumps({'type': 'content', 'text': full_response})}\n\n"

        full_response = _clean_response(full_response)
        db.save_chat_message("assistant", full_response, conversation_id)
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id})}\n\n"

        # Clean up active dispatch tracking
        _active_dispatches.pop(conversation_id, None)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/chat/{conv_id}/cancel")
def cancel_chat(conv_id: int, user: dict = Depends(get_current_user)):
    """Cancel an active agent dispatch for a conversation."""
    conv = db.get_conversation_for_user(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    state = _active_dispatches.get(conv_id)
    if state:
        state["cancel_requested"] = True
        return {"message": "Cancel requested"}
    return {"message": "No active dispatch found"}


# --- Trace Feedback ---

@app.post("/api/traces/{trace_id}/feedback")
def set_trace_feedback(trace_id: int, req: FeedbackRequest, user: dict = Depends(get_current_user)):
    """Set feedback (positive/negative) on an agent trace."""
    if req.rating not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="Rating must be 'positive' or 'negative'")
    updated = db.set_trace_feedback(trace_id, user["id"], req.rating)
    if not updated:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"message": "Feedback recorded"}


# --- Notifications ---

@app.get("/api/notifications")
def list_notifications(unread_only: bool = False, user: dict = Depends(get_current_user)):
    """Get notifications for the current user."""
    return db.get_notifications(user["id"], unread_only=unread_only)


@app.get("/api/notifications/count")
def get_notification_count(user: dict = Depends(get_current_user)):
    """Get unread notification count."""
    return {"count": db.get_unread_notification_count(user["id"])}


@app.patch("/api/notifications/{nid}/read")
def mark_notification_read(nid: int, user: dict = Depends(get_current_user)):
    """Mark a notification as read."""
    updated = db.mark_notification_read(nid, user["id"])
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Marked as read"}


@app.post("/api/notifications/read-all")
def mark_all_read(user: dict = Depends(get_current_user)):
    """Mark all notifications as read."""
    count = db.mark_all_notifications_read(user["id"])
    return {"message": f"Marked {count} notifications as read"}


# --- Goals ---

_goal_planner = GoalPlanner()


@app.post("/api/goals")
def create_goal(req: CreateGoalRequest, user: dict = Depends(get_current_user)):
    """Create a new goal with an AI-generated plan."""
    profile = db.get_profile(user["id"])
    default_resume = db.get_default_resume(user["id"])

    user_context = ""
    if profile:
        parts = []
        if profile.get("target_role"):
            parts.append(f"Target role: {profile['target_role']}")
        if profile.get("skills"):
            parts.append(f"Skills: {', '.join(profile['skills'][:10])}")
        if profile.get("experience_level"):
            parts.append(f"Experience: {profile['experience_level']}")
        user_context = "User context:\n" + "\n".join(parts)

    plan = _goal_planner.create_plan(req.goal_text, user_context)
    goal_id = _goal_planner.save_plan(user["id"], plan)

    return {
        "goal_id": goal_id,
        "title": plan["title"],
        "steps": plan["steps"],
    }


@app.get("/api/goals")
def list_goals(status: str | None = None, user: dict = Depends(get_current_user)):
    """List user's goals with progress."""
    goals = db.get_goals(user["id"], status=status)
    result = []
    for g in goals:
        steps = db.get_goal_steps(g["id"])
        completed = sum(1 for s in steps if s["status"] == "completed")
        result.append({
            **g,
            "total_steps": len(steps),
            "completed_steps": completed,
            "progress": completed / len(steps) if steps else 0,
        })
    return result


@app.get("/api/goals/{goal_id}")
def get_goal_detail(goal_id: int, user: dict = Depends(get_current_user)):
    """Get goal detail with steps."""
    status = _goal_planner.get_plan_status(goal_id, user["id"])
    if not status:
        raise HTTPException(status_code=404, detail="Goal not found")
    return status


@app.post("/api/goals/{goal_id}/execute-next")
def execute_next_goal_step(goal_id: int, user: dict = Depends(get_current_user)):
    """Execute the next pending step in a goal."""
    goal = db.get_goal(goal_id, user["id"])
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    profile = db.get_profile(user["id"])
    default_resume = db.get_default_resume(user["id"])
    resume_text = default_resume["content"] if default_resume else ""

    result = _goal_planner.execute_next_step(
        goal_id=goal_id,
        user_id=user["id"],
        resume_text=resume_text,
        profile=profile,
    )

    if not result:
        return {"message": "No pending steps remaining", "goal_status": "completed"}

    return result


# Active goal auto-executions (for cancellation)
_active_goal_executions: dict[int, dict] = {}  # goal_id -> {"cancel_requested": False}


@app.post("/api/goals/{goal_id}/auto-execute")
def auto_execute_goal(goal_id: int, user: dict = Depends(get_current_user)):
    """Auto-execute all remaining steps in a goal, streaming progress via SSE."""
    goal = db.get_goal(goal_id, user["id"])
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    profile = db.get_profile(user["id"])
    default_resume = db.get_default_resume(user["id"])
    resume_text = default_resume["content"] if default_resume else ""

    # Register for cancellation
    _active_goal_executions[goal_id] = {"cancel_requested": False}

    def cancel_check():
        state = _active_goal_executions.get(goal_id, {})
        return state.get("cancel_requested", False)

    def generate():
        try:
            for event_type, event_data in _goal_planner.auto_execute(
                goal_id=goal_id,
                user_id=user["id"],
                resume_text=resume_text,
                profile=profile,
                cancel_check=cancel_check,
            ):
                yield f"data: {json.dumps({'type': event_type, **event_data})}\n\n"
        finally:
            _active_goal_executions.pop(goal_id, None)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/goals/{goal_id}/cancel")
def cancel_goal_execution(goal_id: int, user: dict = Depends(get_current_user)):
    """Cancel an auto-executing goal."""
    goal = db.get_goal(goal_id, user["id"])
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    state = _active_goal_executions.get(goal_id)
    if state:
        state["cancel_requested"] = True
        return {"message": "Cancel requested"}
    return {"message": "No active execution found"}


# --- Suggestions ---

@app.get("/api/suggestions")
def get_suggestions(user: dict = Depends(get_current_user)):
    """Get proactive suggestions for the user."""
    from .suggestions import SuggestionEngine
    engine = SuggestionEngine(user["id"])
    return engine.generate()


# --- WebSocket Real-Time Push (Gap 1) ---

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time push notifications.

    Auth: first message must be {"type": "auth", "token": "..."}.
    After auth, keeps connection alive with heartbeat pings.
    """
    await ws.accept()
    user_id = await authenticate_ws(ws)
    if user_id is None:
        await ws.close(code=4001)
        return

    # Re-register with manager (authenticate_ws already accepted)
    if user_id not in ws_manager._connections:
        ws_manager._connections[user_id] = []
    ws_manager._connections[user_id].append(ws)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "ping":
                    await ws.send_json({"type": "pong"})
                elif msg_type == "cancel" and msg.get("conversation_id"):
                    # Cancel active dispatch via WebSocket
                    conv_id = msg["conversation_id"]
                    state = _active_dispatches.get(conv_id)
                    if state:
                        state["cancel_requested"] = True
                        await ws.send_json({"type": "cancel_ack", "conversation_id": conv_id})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(ws, user_id)


# --- Autonomous Tasks (Gap 5) ---

class LaunchTaskRequest(BaseModel):
    task_type: str  # "job_monitor", "app_tracker", "company_deep_dive"
    config: dict = {}


@app.post("/api/tasks")
def launch_task(req: LaunchTaskRequest, user: dict = Depends(get_current_user)):
    """Launch an autonomous background task."""
    task_db_id = db.create_autonomous_task(
        user_id=user["id"],
        task_type=req.task_type,
        config=json.dumps(req.config),
    )

    # Dispatch to Celery
    celery_task_id = None
    try:
        if req.task_type == "company_deep_dive":
            company = req.config.get("company_name", "Unknown")
            from .tasks.company_deep_dive import research_company
            result = research_company.delay(
                user_id=user["id"],
                company_name=company,
                task_db_id=task_db_id,
            )
            celery_task_id = result.id
        elif req.task_type == "job_monitor":
            from .tasks.job_monitor import monitor_jobs_for_all_users
            result = monitor_jobs_for_all_users.delay()
            celery_task_id = result.id
        elif req.task_type == "app_tracker":
            from .tasks.app_tracker import track_all_applications
            result = track_all_applications.delay()
            celery_task_id = result.id
        else:
            raise HTTPException(status_code=400, detail=f"Unknown task type: {req.task_type}")

        if celery_task_id:
            db.update_autonomous_task(task_db_id, celery_task_id=celery_task_id, status="running")
    except ImportError:
        # Celery/Redis not available — mark as failed
        db.update_autonomous_task(task_db_id, status="failed")
        raise HTTPException(status_code=503, detail="Task queue not available (Redis/Celery not running)")

    return {"task_id": task_db_id, "celery_task_id": celery_task_id, "status": "running"}


@app.get("/api/tasks")
def list_tasks(status: str | None = None, user: dict = Depends(get_current_user)):
    """List autonomous tasks for the current user."""
    return db.get_user_tasks(user["id"], status=status)


@app.get("/api/tasks/{task_id}")
def get_task(task_id: int, user: dict = Depends(get_current_user)):
    """Get status of a specific autonomous task."""
    task = db.get_autonomous_task(task_id)
    if not task or task["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Task not found")
    results = db.get_task_results(task_id)
    return {**task, "results": results}


@app.delete("/api/tasks/{task_id}")
def cancel_task(task_id: int, user: dict = Depends(get_current_user)):
    """Cancel a running autonomous task."""
    task = db.get_autonomous_task(task_id)
    if not task or task["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] == "running" and task.get("celery_task_id"):
        try:
            from .celery_app import celery_app as celery
            celery.control.revoke(task["celery_task_id"], terminate=True)
        except Exception:
            pass

    db.update_autonomous_task(task_id, status="cancelled")
    return {"message": "Task cancelled"}


# --- Goal Suggestions (Gap 3) ---

@app.get("/api/goals/suggested")
def get_suggested_goals(user: dict = Depends(get_current_user)):
    """Get agent-suggested goals awaiting approval."""
    return db.get_suggested_goals(user["id"])


@app.post("/api/goals/{goal_id}/approve")
def approve_suggested_goal(goal_id: int, user: dict = Depends(get_current_user)):
    """Approve a suggested goal — makes it active."""
    updated = db.approve_goal(goal_id, user["id"])
    if not updated:
        raise HTTPException(status_code=404, detail="Suggested goal not found")
    return {"message": "Goal approved and activated"}


@app.post("/api/goals/{goal_id}/dismiss")
def dismiss_suggested_goal(goal_id: int, user: dict = Depends(get_current_user)):
    """Dismiss a suggested goal."""
    updated = db.dismiss_goal(goal_id, user["id"])
    if not updated:
        raise HTTPException(status_code=404, detail="Suggested goal not found")
    return {"message": "Goal dismissed"}


# Serve React frontend for all non-API routes
@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    """Serve the React SPA for all non-API routes."""
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "KaziAI API is running. Frontend not built yet."}
