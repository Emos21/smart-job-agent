from typing import Any

from .base import Tool


class EmailDrafterTool(Tool):
    """Generates professional follow-up emails for the job application process.

    Creates thank-you emails after interviews, follow-up emails for
    pending applications, and salary negotiation emails — all tailored
    to the specific role, company, and conversation context.
    """

    @property
    def name(self) -> str:
        return "draft_email"

    @property
    def description(self) -> str:
        return (
            "Draft a professional follow-up email for the job application process. "
            "Supports thank-you emails after interviews, follow-up emails for "
            "pending decisions, and salary negotiation emails. Tailored to the "
            "role, company, and specific conversation points."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "email_type": {
                    "type": "string",
                    "description": "Type of email: 'thank_you', 'follow_up', 'negotiation', 'withdrawal'",
                    "enum": ["thank_you", "follow_up", "negotiation", "withdrawal"],
                },
                "role_title": {
                    "type": "string",
                    "description": "The job title being applied for",
                },
                "company_name": {
                    "type": "string",
                    "description": "The company name",
                },
                "interviewer_name": {
                    "type": "string",
                    "description": "Name of the interviewer or hiring manager",
                    "default": "",
                },
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key discussion points or topics to reference",
                    "default": [],
                },
                "additional_context": {
                    "type": "string",
                    "description": "Any additional context (e.g., salary offer amount for negotiation)",
                    "default": "",
                },
            },
            "required": ["email_type", "role_title", "company_name"],
        }

    def _draft_thank_you(
        self, role: str, company: str, interviewer: str, key_points: list[str]
    ) -> dict[str, str]:
        """Draft a post-interview thank-you email."""
        greeting = f"Dear {interviewer}," if interviewer else "Dear Hiring Team,"

        # Build personalized middle paragraphs from key points
        points_text = ""
        if key_points:
            points_text = (
                "\n\nI particularly enjoyed our conversation about "
                + (" and ".join(key_points[:2]) if len(key_points) <= 2
                   else ", ".join(key_points[:-1]) + f", and {key_points[-1]}")
                + ". It reinforced my enthusiasm for the opportunity and how my "
                "experience aligns with the team's goals."
            )

        body = f"""{greeting}

Thank you for taking the time to discuss the {role} position at {company}. I appreciated learning more about the team and the challenges you're tackling.{points_text}

I'm excited about the possibility of contributing to {company} and am confident that my skills and experience would be a strong fit for this role.

Please don't hesitate to reach out if you need any additional information. I look forward to hearing about the next steps.

Best regards"""

        return {
            "subject": f"Thank you — {role} Interview at {company}",
            "body": body,
        }

    def _draft_follow_up(
        self, role: str, company: str, interviewer: str
    ) -> dict[str, str]:
        """Draft a follow-up email for a pending application."""
        greeting = f"Dear {interviewer}," if interviewer else "Dear Hiring Team,"

        body = f"""{greeting}

I hope this message finds you well. I wanted to follow up on my application for the {role} position at {company}.

I remain very interested in this opportunity and would welcome any updates on the status of the hiring process. I'm happy to provide any additional information that might be helpful in your decision.

Thank you for your time and consideration.

Best regards"""

        return {
            "subject": f"Following up — {role} Position at {company}",
            "body": body,
        }

    def _draft_negotiation(
        self, role: str, company: str, interviewer: str,
        key_points: list[str], context: str
    ) -> dict[str, str]:
        """Draft a salary negotiation email."""
        greeting = f"Dear {interviewer}," if interviewer else "Dear Hiring Team,"

        # Build justification from key points
        justification = ""
        if key_points:
            bullet_points = "\n".join(f"  - {point}" for point in key_points)
            justification = f"\n\nI base this on several factors:\n{bullet_points}"

        context_line = ""
        if context:
            context_line = f"\n\n{context}"

        body = f"""{greeting}

Thank you for extending the offer for the {role} position at {company}. I'm excited about the opportunity to join the team.

After careful consideration, I'd like to discuss the compensation package. Based on my research of market rates for this role and the value I would bring to the team, I believe there is room to adjust the offer.{justification}{context_line}

I'm enthusiastic about {company} and confident we can find a package that works for both of us. I'd love to discuss this further at your convenience.

Best regards"""

        return {
            "subject": f"Re: {role} Offer — Compensation Discussion",
            "body": body,
        }

    def _draft_withdrawal(
        self, role: str, company: str, interviewer: str
    ) -> dict[str, str]:
        """Draft a professional withdrawal email."""
        greeting = f"Dear {interviewer}," if interviewer else "Dear Hiring Team,"

        body = f"""{greeting}

Thank you for considering me for the {role} position at {company}. After careful thought, I have decided to withdraw my application at this time.

This was not an easy decision, and I truly appreciate the time and consideration your team invested in the process. I have great respect for {company} and the work you're doing.

I hope our paths may cross again in the future, and I wish you and the team continued success.

Best regards"""

        return {
            "subject": f"Withdrawal — {role} Application at {company}",
            "body": body,
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        email_type = kwargs["email_type"]
        role = kwargs["role_title"]
        company = kwargs["company_name"]
        interviewer = kwargs.get("interviewer_name", "")
        key_points = kwargs.get("key_points", [])
        context = kwargs.get("additional_context", "")

        drafters = {
            "thank_you": lambda: self._draft_thank_you(role, company, interviewer, key_points),
            "follow_up": lambda: self._draft_follow_up(role, company, interviewer),
            "negotiation": lambda: self._draft_negotiation(role, company, interviewer, key_points, context),
            "withdrawal": lambda: self._draft_withdrawal(role, company, interviewer),
        }

        drafter = drafters.get(email_type)
        if not drafter:
            return {"success": False, "error": f"Unknown email type: {email_type}"}

        email = drafter()

        return {
            "success": True,
            "email_type": email_type,
            "subject": email["subject"],
            "body": email["body"],
            "tips": self._get_tips(email_type),
        }

    def _get_tips(self, email_type: str) -> list[str]:
        """Return tips for the email type."""
        tips = {
            "thank_you": [
                "Send within 24 hours of the interview",
                "Reference specific topics from the conversation",
                "Keep it concise — 3-4 short paragraphs max",
            ],
            "follow_up": [
                "Wait at least a week after the expected decision date",
                "Keep the tone positive and patient",
                "Reaffirm your interest without being pushy",
            ],
            "negotiation": [
                "Always negotiate — most employers expect it",
                "Lead with enthusiasm for the role, then discuss compensation",
                "Back up your ask with market data and your specific value",
                "Consider the full package: base, equity, benefits, flexibility",
            ],
            "withdrawal": [
                "Be gracious and professional — you may want to work there later",
                "You don't need to explain your reasons in detail",
                "Send promptly so they can move forward with other candidates",
            ],
        }
        return tips.get(email_type, [])
