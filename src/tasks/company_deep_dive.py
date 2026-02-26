"""Company deep dive task — on-demand deep research about a company.

Triggered by user action, not periodic. Runs the company research tool
and saves detailed results. Checkpoints research progress.
"""

import json

from ..celery_app import celery_app
from .. import database as db
from .base_task import AutonomousTask


@celery_app.task(base=AutonomousTask, bind=True, name="src.tasks.company_deep_dive.research_company")
def research_company(self, user_id: int, company_name: str, task_db_id: int | None = None):
    """Run deep research on a company and create a detailed report."""
    self._task_db_id = task_db_id

    # Restore checkpoint if resuming
    state = None
    if task_db_id:
        state = self.restore(task_db_id)

    result = {
        "company": company_name,
        "sections": {},
    }

    # If we have a checkpoint, resume from where we left off
    if state:
        result = state.get("result", result)

    # Research the company
    try:
        from ..tools.company_researcher import CompanyResearcherTool
        tool = CompanyResearcherTool()
        research = tool.execute(company_name=company_name)
        result["sections"]["overview"] = research
        self.checkpoint({"result": result, "phase": "overview_done"})
    except Exception as e:
        result["sections"]["overview"] = {"error": str(e)}

    # Store result
    if task_db_id:
        try:
            db.create_task_result(
                task_id=task_db_id,
                result_type="company_research",
                data=json.dumps(result),
            )
        except Exception:
            pass

    # Notify user
    db.create_notification(
        user_id=user_id,
        type="task_complete",
        title=f"Company research: {company_name}",
        message=f"Deep dive research on {company_name} is complete. Check your Tasks tab.",
        data=json.dumps({"task_db_id": task_db_id, "company": company_name}),
    )

    return result
