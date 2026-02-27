"""Goal planner that decomposes high-level career goals into agent-executable steps.

"Help me land a backend role at Stripe" → 5 concrete steps with agent assignments.
Supports auto-execution with re-planning between steps.
"""

import json
import os
from dataclasses import dataclass

from openai import OpenAI
from dotenv import load_dotenv

from .. import database as db
from .orchestrator import Orchestrator
from .router import RoutingDecision

load_dotenv()


REPLAN_PROMPT = """You are a plan evaluator. After completing a step in a multi-step career plan, decide if the plan should continue as-is or be adjusted.

Given: the step that just completed, its output, and the remaining steps.

DECISIONS:
- "continue": The step succeeded, proceed with the next step as planned.
- "modify_step": The next step needs adjustment based on what we learned. Provide a new description.
- "add_step": Insert an additional step before the next one. Provide title, description, agent_name.
- "skip_next": The next step is no longer needed (already covered by this step's output).

Respond with ONLY valid JSON (no markdown):
{"action": "continue|modify_step|add_step|skip_next", "reason": "brief explanation", "new_title": "", "new_description": "", "agent_name": ""}"""


@dataclass
class PlanAdjustment:
    """Result of re-evaluating a plan between steps."""
    action: str       # "continue", "modify_step", "add_step", "skip_next"
    reason: str
    new_title: str = ""
    new_description: str = ""
    agent_name: str = ""

PLANNING_PROMPT = """You are a career goal planner. Given a user's career goal, decompose it into 3-6 concrete, actionable steps that can each be handled by a specialized AI agent.

AVAILABLE AGENTS:
- scout: Searches for jobs, researches companies, explores the market
- match: Analyzes resume vs job description, scores ATS compatibility, identifies gaps
- forge: Writes cover letters, rewrites resume bullets, creates application materials
- coach: Prepares interview questions, provides talking points, offers strategic advice

RULES:
- Each step should be a clear, specific action (not vague)
- Assign exactly one agent per step
- Order steps logically (research before analysis, analysis before writing)
- 3-6 steps total (fewer for simple goals, more for complex)
- Step titles should be concise (under 60 chars)

Respond with ONLY valid JSON (no markdown):
{
  "title": "Short goal title (under 60 chars)",
  "steps": [
    {"title": "Step title", "description": "What this step does", "agent_name": "scout|match|forge|coach"},
    ...
  ]
}"""


class GoalPlanner:
    """Decomposes career goals into trackable, multi-step plans."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            provider = os.getenv("LLM_PROVIDER", "groq")
            if provider == "ollama":
                self._client = OpenAI(
                    api_key="ollama",
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                )
            else:
                api_key = os.getenv("GROQ_API_KEY")
                self._client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
        return self._client

    def create_plan(self, goal_text: str, user_context: str = "") -> dict:
        """Decompose a goal into agent steps and persist to database.

        Returns: {"goal_id": int, "title": str, "steps": [...]}
        """
        try:
            response = self.client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=[
                    {"role": "system", "content": PLANNING_PROMPT},
                    {"role": "user", "content": f"Goal: {goal_text}\n\n{user_context}"},
                ],
                max_tokens=600,
                temperature=0.2,
            )

            raw = response.choices[0].message.content or "{}"
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            data = json.loads(raw)
            return self._normalize_plan(data, goal_text)

        except Exception:
            # Fallback: create a generic plan
            return {
                "title": goal_text[:60],
                "steps": [
                    {"title": "Research opportunities", "description": f"Search for relevant positions: {goal_text}", "agent_name": "scout"},
                    {"title": "Analyze fit", "description": "Compare your background against requirements", "agent_name": "match"},
                    {"title": "Prepare materials", "description": "Write tailored cover letter and resume", "agent_name": "forge"},
                    {"title": "Prep for interviews", "description": "Practice likely interview questions", "agent_name": "coach"},
                ],
            }

    def _normalize_plan(self, data: dict, goal_text: str) -> dict:
        """Validate and normalize the plan data."""
        valid_agents = {"scout", "match", "forge", "coach"}

        title = data.get("title", goal_text[:60])
        steps = data.get("steps", [])

        normalized = []
        for step in steps[:6]:
            if not isinstance(step, dict) or "title" not in step:
                continue
            agent = step.get("agent_name", "scout")
            if agent not in valid_agents:
                agent = "scout"
            normalized.append({
                "title": step["title"][:60],
                "description": step.get("description", ""),
                "agent_name": agent,
            })

        if not normalized:
            normalized = [
                {"title": "Research opportunities", "description": goal_text, "agent_name": "scout"},
            ]

        return {"title": title, "steps": normalized}

    def save_plan(self, user_id: int, plan: dict) -> int:
        """Persist a plan to the database as a goal with steps."""
        goal_id = db.create_goal(user_id, plan["title"], plan.get("description", ""))

        for i, step in enumerate(plan["steps"], 1):
            db.add_goal_step(
                goal_id=goal_id,
                step_number=i,
                title=step["title"],
                description=step.get("description", ""),
                agent_name=step.get("agent_name", ""),
            )

        return goal_id

    def execute_next_step(
        self,
        goal_id: int,
        user_id: int,
        resume_text: str = "",
        profile: dict | None = None,
    ) -> dict | None:
        """Find and execute the next pending step for a goal.

        Returns the step result dict or None if no pending steps.
        """
        step = db.get_next_pending_step(goal_id)
        if not step:
            return None

        goal = db.get_goal(goal_id, user_id)
        if not goal:
            return None

        # Mark step as in progress
        db.update_goal_step(step["id"], "in_progress")

        # Build a routing decision for this single agent
        routing = RoutingDecision(
            intent="goal_step",
            agents=[step["agent_name"]],
            extracted_context={"role": goal["title"]},
            reasoning=f"Executing goal step: {step['title']}",
        )

        orchestrator = Orchestrator(provider=os.getenv("LLM_PROVIDER", "groq"))
        results = orchestrator.dispatch(
            routing=routing,
            user_message=f"{goal['title']}: {step['description']}",
            resume_text=resume_text,
            profile=profile,
            user_id=user_id,
        )

        if results and results[0].success:
            db.update_goal_step(step["id"], "completed", output=results[0].output)
            output = results[0].output
        else:
            error_msg = results[0].output if results else "Agent did not produce output"
            db.update_goal_step(step["id"], "failed", output=error_msg)
            output = error_msg

        # Check if all steps are done
        remaining = db.get_next_pending_step(goal_id)
        if not remaining:
            # Check if any steps are still in_progress
            all_steps = db.get_goal_steps(goal_id)
            if all(s["status"] in ("completed", "skipped", "failed") for s in all_steps):
                db.update_goal_status(goal_id, "completed")

        return {
            "step_id": step["id"],
            "step_title": step["title"],
            "agent_name": step["agent_name"],
            "output": output,
            "status": "completed" if results and results[0].success else "failed",
        }

    def get_plan_status(self, goal_id: int, user_id: int) -> dict | None:
        """Return goal + all steps with status."""
        goal = db.get_goal(goal_id, user_id)
        if not goal:
            return None

        steps = db.get_goal_steps(goal_id)
        completed = sum(1 for s in steps if s["status"] == "completed")

        return {
            **goal,
            "steps": steps,
            "total_steps": len(steps),
            "completed_steps": completed,
            "progress": completed / len(steps) if steps else 0,
        }

    def auto_execute(
        self,
        goal_id: int,
        user_id: int,
        resume_text: str = "",
        profile: dict | None = None,
        cancel_check=None,
    ):
        """Auto-execute all remaining steps, yielding SSE-compatible events.

        Yields tuples of (event_type, event_data):
          - ("goal_step_start", {step_number, title, agent})
          - ("goal_step_complete", {step_number, status, output_preview})
          - ("goal_replan", {adjustment, reason})
          - ("goal_complete", {status})
        """
        goal = db.get_goal(goal_id, user_id)
        if not goal:
            yield ("goal_complete", {"status": "not_found"})
            return

        max_total_steps = 10  # Safety: max steps including dynamically added ones

        for _ in range(max_total_steps):
            # Check cancellation
            if cancel_check and cancel_check():
                yield ("goal_complete", {"status": "cancelled"})
                return

            step = db.get_next_pending_step(goal_id)
            if not step:
                break

            yield ("goal_step_start", {
                "step_number": step["step_number"],
                "title": step["title"],
                "agent": step["agent_name"],
            })

            # Execute the step
            db.update_goal_step(step["id"], "in_progress")

            routing = RoutingDecision(
                intent="goal_step",
                agents=[step["agent_name"]],
                extracted_context={"role": goal["title"]},
                reasoning=f"Executing goal step: {step['title']}",
            )

            orchestrator = Orchestrator(provider=os.getenv("LLM_PROVIDER", "groq"))
            results = orchestrator.dispatch(
                routing=routing,
                user_message=f"{goal['title']}: {step['description']}",
                resume_text=resume_text,
                profile=profile,
                user_id=user_id,
                cancel_check=cancel_check,
            )

            if results and results[0].success:
                db.update_goal_step(step["id"], "completed", output=results[0].output)
                output = results[0].output
                step_status = "completed"
            else:
                error_msg = results[0].output if results else "Agent did not produce output"
                db.update_goal_step(step["id"], "failed", output=error_msg)
                output = error_msg
                step_status = "failed"

            yield ("goal_step_complete", {
                "step_number": step["step_number"],
                "status": step_status,
                "output_preview": output[:500],
            })

            # Re-evaluate plan between steps
            if step_status == "completed":
                remaining_steps = db.get_goal_steps(goal_id)
                pending = [s for s in remaining_steps if s["status"] == "pending"]
                if pending:
                    adjustment = self._re_evaluate_plan(
                        completed_step=step,
                        step_output=output,
                        remaining_steps=pending,
                    )

                    if adjustment.action != "continue":
                        yield ("goal_replan", {
                            "adjustment": adjustment.action,
                            "reason": adjustment.reason,
                        })

                        if adjustment.action == "skip_next":
                            # Skip the next pending step
                            next_step = pending[0]
                            db.update_goal_step(next_step["id"], "skipped", output=f"Skipped: {adjustment.reason}")

                        elif adjustment.action == "modify_step" and pending:
                            # Update the next step's description
                            next_step = pending[0]
                            if adjustment.new_description:
                                db.update_goal_step(next_step["id"], "pending", output="")
                                # Re-create step with modified description
                                conn = db.get_db()
                                conn.execute(
                                    "UPDATE goal_steps SET description = ? WHERE id = ?",
                                    (adjustment.new_description, next_step["id"]),
                                )
                                conn.commit()
                                conn.close()

                        elif adjustment.action == "add_step":
                            # Insert a new step
                            if adjustment.new_title and adjustment.agent_name:
                                new_step_num = pending[0]["step_number"]
                                # Shift existing steps up
                                conn = db.get_db()
                                conn.execute(
                                    "UPDATE goal_steps SET step_number = step_number + 1 WHERE goal_id = ? AND step_number >= ? AND status = 'pending'",
                                    (goal_id, new_step_num),
                                )
                                conn.commit()
                                conn.close()
                                db.add_goal_step(
                                    goal_id=goal_id,
                                    step_number=new_step_num,
                                    title=adjustment.new_title,
                                    description=adjustment.new_description,
                                    agent_name=adjustment.agent_name,
                                )

        # Check final status
        all_steps = db.get_goal_steps(goal_id)
        if all(s["status"] in ("completed", "skipped", "failed") for s in all_steps):
            db.update_goal_status(goal_id, "completed")
            yield ("goal_complete", {"status": "completed"})
        else:
            yield ("goal_complete", {"status": "partial"})

    def _re_evaluate_plan(self, completed_step: dict, step_output: str, remaining_steps: list[dict]) -> PlanAdjustment:
        """Cheap LLM call to decide if the plan should be adjusted after a step completes."""
        try:
            remaining_summary = "\n".join(
                f"- Step {s['step_number']}: {s['title']} ({s['agent_name']})" for s in remaining_steps
            )
            user_msg = (
                f"Completed step: {completed_step['title']} ({completed_step['agent_name']})\n"
                f"Output preview: {step_output[:800]}\n\n"
                f"Remaining steps:\n{remaining_summary}"
            )

            response = self.client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
                messages=[
                    {"role": "system", "content": REPLAN_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=200,
                temperature=0.1,
            )

            raw = response.choices[0].message.content or "{}"
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            data = json.loads(raw)
            action = data.get("action", "continue")
            valid_actions = {"continue", "modify_step", "add_step", "skip_next"}
            if action not in valid_actions:
                action = "continue"

            valid_agents = {"scout", "match", "forge", "coach"}
            agent = data.get("agent_name", "")
            if agent and agent not in valid_agents:
                agent = ""

            return PlanAdjustment(
                action=action,
                reason=str(data.get("reason", ""))[:200],
                new_title=str(data.get("new_title", ""))[:60],
                new_description=str(data.get("new_description", "")),
                agent_name=agent,
            )

        except Exception:
            return PlanAdjustment(action="continue", reason="Re-plan fallback")
