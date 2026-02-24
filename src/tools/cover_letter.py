from typing import Any

from .base import Tool


class CoverLetterTool(Tool):
    """Generates a structured cover letter framework.

    Takes the analysis results (matched skills, gaps, company info)
    and produces a cover letter outline. The actual prose is generated
    by the agent's LLM reasoning, but this tool structures the key
    points that should be addressed.
    """

    @property
    def name(self) -> str:
        return "generate_cover_letter"

    @property
    def description(self) -> str:
        return (
            "Generate a tailored cover letter framework based on job analysis results. "
            "Takes matched skills, missing skills, company context, and candidate "
            "background to produce a structured cover letter."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "candidate_name": {
                    "type": "string",
                    "description": "The candidate's full name",
                },
                "company_name": {
                    "type": "string",
                    "description": "The company being applied to",
                },
                "role_title": {
                    "type": "string",
                    "description": "The job title being applied for",
                },
                "matched_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills that match the job requirements",
                },
                "missing_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required skills the candidate lacks",
                },
                "key_experiences": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relevant experiences to highlight",
                },
                "company_context": {
                    "type": "string",
                    "description": "Brief context about the company",
                    "default": "",
                },
            },
            "required": [
                "candidate_name",
                "company_name",
                "role_title",
                "matched_skills",
                "missing_skills",
                "key_experiences",
            ],
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        name = kwargs["candidate_name"]
        company = kwargs["company_name"]
        role = kwargs["role_title"]
        matched = kwargs["matched_skills"]
        missing = kwargs["missing_skills"]
        experiences = kwargs["key_experiences"]
        company_ctx = kwargs.get("company_context", "")

        # Build strength points from matched skills
        strength_points = []
        for skill in matched[:5]:  # Top 5 matches
            strength_points.append(
                f"Demonstrated proficiency in {skill}"
            )

        # Build growth narrative for missing skills
        growth_points = []
        for skill in missing[:3]:  # Top 3 gaps
            growth_points.append(
                f"Eager to deepen expertise in {skill} — "
                f"with a strong foundation in related areas"
            )

        # Structure the letter
        letter = {
            "opening": (
                f"Dear Hiring Manager,\n\n"
                f"I am writing to express my interest in the {role} position "
                f"at {company}."
            ),
            "company_connection": (
                f"What draws me to {company} is {company_ctx}"
                if company_ctx
                else f"I am excited about the opportunity to contribute to {company}'s mission."
            ),
            "strengths_paragraph": (
                "My background aligns well with this role:\n"
                + "\n".join(f"  - {point}" for point in strength_points)
            ),
            "experience_highlights": (
                "Key experiences I would bring:\n"
                + "\n".join(f"  - {exp}" for exp in experiences[:4])
            ),
            "growth_narrative": (
                "Areas where I am actively growing:\n"
                + "\n".join(f"  - {point}" for point in growth_points)
            ) if growth_points else "",
            "closing": (
                f"\nI would welcome the opportunity to discuss how my skills "
                f"and experience can contribute to your team.\n\n"
                f"Best regards,\n{name}"
            ),
        }

        # Combine into full text
        sections = [
            letter["opening"],
            letter["company_connection"],
            letter["strengths_paragraph"],
            letter["experience_highlights"],
        ]
        if letter["growth_narrative"]:
            sections.append(letter["growth_narrative"])
        sections.append(letter["closing"])

        full_letter = "\n\n".join(sections)

        return {
            "success": True,
            "cover_letter": full_letter,
            "structure": letter,
            "stats": {
                "strengths_highlighted": len(strength_points),
                "gaps_addressed": len(growth_points),
                "experiences_included": min(len(experiences), 4),
            },
        }
