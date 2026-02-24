import os
from typing import Any

from .base import Tool


class ResumeAnalyzerTool(Tool):
    """Reads and structures resume content for analysis.

    Loads a resume from a text file and organizes the content
    so the agent can compare it against job requirements.
    """

    @property
    def name(self) -> str:
        return "analyze_resume"

    @property
    def description(self) -> str:
        return (
            "Read a resume from a file and extract its content for analysis. "
            "Returns the structured text content of the resume."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the resume text file",
                },
            },
            "required": ["file_path"],
        }

    def _extract_sections(self, text: str) -> dict[str, str]:
        """Identify resume sections by common header patterns."""
        sections = {}
        current_section = "header"
        current_lines = []

        section_markers = [
            "experience", "education", "skills", "projects",
            "certifications", "summary", "objective", "awards",
            "publications", "languages", "technical skills",
            "work experience", "professional experience",
        ]

        for line in text.split("\n"):
            stripped = line.strip().lower()
            # Check if this line is a section header
            clean = stripped.rstrip(":").rstrip()
            if clean in section_markers:
                if current_lines:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = clean
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_section] = "\n".join(current_lines).strip()

        return sections

    def execute(self, **kwargs) -> dict[str, Any]:
        file_path = kwargs["file_path"]

        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"Resume file not found: {file_path}",
            }

        try:
            with open(file_path, "r") as f:
                text = f.read()
        except IOError as e:
            return {
                "success": False,
                "error": f"Failed to read resume: {str(e)}",
            }

        if not text.strip():
            return {
                "success": False,
                "error": "Resume file is empty",
            }

        sections = self._extract_sections(text)

        return {
            "success": True,
            "raw_text": text[:4000],
            "sections": sections,
            "char_count": len(text),
        }
