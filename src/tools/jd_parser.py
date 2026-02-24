import json
import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from .base import Tool


class JDParserTool(Tool):
    """Parses job descriptions from raw text or URLs.

    Extracts structured information: role title, company, required skills,
    preferred skills, experience level, responsibilities, and keywords.
    Handles both plain text input and web URLs.
    """

    @property
    def name(self) -> str:
        return "parse_job_description"

    @property
    def description(self) -> str:
        return (
            "Parse a job description from text or URL. Extracts role title, "
            "company name, required skills, preferred skills, experience level, "
            "responsibilities, and important keywords."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The job description text or a URL to fetch it from",
                },
                "is_url": {
                    "type": "boolean",
                    "description": "Whether the source is a URL to fetch",
                    "default": False,
                },
            },
            "required": ["source"],
        }

    def _fetch_from_url(self, url: str) -> str:
        """Fetch and extract text content from a job posting URL."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Collapse excessive whitespace while preserving structure
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:8000]  # Limit to avoid token overflow

    def _extract_sections(self, text: str) -> dict[str, str]:
        """Pull out common JD sections using header patterns."""
        sections = {}
        current_section = "overview"
        current_lines = []

        for line in text.split("\n"):
            stripped = line.strip()
            # Detect section headers (lines that look like headings)
            if stripped and len(stripped) < 80 and stripped.endswith(":"):
                if current_lines:
                    sections[current_section] = "\n".join(current_lines)
                current_section = stripped.rstrip(":").lower()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_section] = "\n".join(current_lines)

        return sections

    def execute(self, **kwargs) -> dict[str, Any]:
        source = kwargs["source"]
        is_url = kwargs.get("is_url", False)

        if is_url:
            try:
                text = self._fetch_from_url(source)
            except requests.RequestException as e:
                return {
                    "success": False,
                    "error": f"Failed to fetch URL: {str(e)}",
                }
        else:
            text = source

        sections = self._extract_sections(text)

        return {
            "success": True,
            "raw_text": text[:4000],
            "sections": sections,
            "char_count": len(text),
        }
