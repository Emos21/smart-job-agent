import os
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

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


class RenameConversationRequest(BaseModel):
    title: str


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

    orchestrator = Orchestrator(provider="groq")
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


# --- Chat (conversation-scoped, agentic with function calling) ---

SYSTEM_PROMPT = """You are KaziAI, an intelligent AI career assistant powered by a multi-agent system. You help job seekers with:
- Searching and finding relevant jobs across multiple job boards
- Analyzing job descriptions and scoring resumes against ATS systems
- Writing tailored cover letters and rewriting resume bullets
- Interview preparation with targeted questions and talking points
- Mock interviews with STAR method evaluation
- Company research for interview context
- GitHub portfolio analysis to identify demonstrable skills
- Salary research with market data
- Follow-up email drafting (thank-you, negotiation, follow-up)
- Learning path generation for skill gaps
- Career advice and strategy

You have access to real tools that search job boards, score resumes, analyze GitHub profiles, research salaries, conduct mock interviews, generate materials, and more.
When a user asks you to do something, USE YOUR TOOLS to actually do it — don't just give generic advice.

Guidelines:
- Be conversational, helpful, and proactive
- Give specific, actionable responses backed by tool results
- Use markdown formatting for readability
- When searching for jobs, extract relevant keywords from the user's message
- When the user provides a job description, use the analysis tools
- For mock interviews, generate a question first, then evaluate when the user answers
- Always explain what you found and give actionable next steps"""


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
    return registry

CHAT_REGISTRY = _build_chat_registry()
MAX_TOOL_ROUNDS = 3


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


def _execute_tool_call(name: str, arguments: dict) -> dict:
    """Execute a tool by name and return its result."""
    tool = CHAT_REGISTRY.get(name)
    if tool is None:
        return {"success": False, "error": f"Unknown tool: {name}"}
    try:
        return tool.execute(**arguments)
    except Exception as e:
        return {"success": False, "error": f"Tool failed: {str(e)}"}


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

    # Build conversation messages from history
    history = db.get_chat_history(conversation_id, limit=20)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[:-1]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": req.message})

    client = _get_llm_client()
    if not client:
        response = "AI backend not configured. Please set GROQ_API_KEY in your .env file."
        db.save_chat_message("assistant", response, conversation_id)
        return {"response": response, "conversation_id": conversation_id}

    # Agentic loop: let the LLM call tools, feed results back, repeat
    tool_specs = CHAT_REGISTRY.to_openai_specs()
    response = ""

    try:
        for _round in range(MAX_TOOL_ROUNDS + 1):
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                tools=tool_specs if _round < MAX_TOOL_ROUNDS else None,
                tool_choice="auto" if _round < MAX_TOOL_ROUNDS else None,
                max_tokens=1500,
                temperature=0.7,
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
        response = f"I ran into an issue processing your request: {str(e)[:200]}. Please try again."

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
