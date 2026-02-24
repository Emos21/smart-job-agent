import os
import tempfile

import pytest

from src.tools.base import ToolRegistry
from src.tools.jd_parser import JDParserTool
from src.tools.resume_analyzer import ResumeAnalyzerTool
from src.tools.skills_matcher import SkillsMatcherTool
from src.tools.cover_letter import CoverLetterTool


class TestToolRegistry:
    def test_register_and_retrieve(self):
        registry = ToolRegistry()
        tool = JDParserTool()
        registry.register(tool)

        assert registry.get("parse_job_description") is tool
        assert registry.get("nonexistent") is None

    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register(JDParserTool())
        registry.register(SkillsMatcherTool())

        tools = registry.list_tools()
        assert len(tools) == 2

    def test_openai_spec_format(self):
        registry = ToolRegistry()
        registry.register(JDParserTool())

        specs = registry.to_openai_specs()
        assert len(specs) == 1
        assert specs[0]["type"] == "function"
        assert "name" in specs[0]["function"]
        assert "description" in specs[0]["function"]
        assert "parameters" in specs[0]["function"]


class TestJDParser:
    def test_parse_text(self):
        jd_text = """Software Engineer
        Acme Corp

        Requirements:
        - Python
        - PostgreSQL
        - 3+ years experience

        Preferred:
        - Docker experience
        - CI/CD knowledge
        """
        tool = JDParserTool()
        result = tool.execute(source=jd_text)

        assert result["success"] is True
        assert result["char_count"] > 0
        assert "raw_text" in result

    def test_section_extraction(self):
        jd_text = """Overview of the role.

        Requirements:
        Python, Go, and Rust experience.

        Responsibilities:
        Build backend systems.
        """
        tool = JDParserTool()
        result = tool.execute(source=jd_text)

        assert result["success"] is True
        assert "sections" in result


class TestResumeAnalyzer:
    def test_analyze_resume_file(self):
        resume_text = """John Doe
        Software Engineer

        Skills:
        Python, JavaScript, Docker

        Experience:
        Built web applications for 3 years.

        Education:
        BS Computer Science
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write(resume_text)
            temp_path = f.name

        try:
            tool = ResumeAnalyzerTool()
            result = tool.execute(file_path=temp_path)

            assert result["success"] is True
            assert "sections" in result
            assert result["char_count"] > 0
        finally:
            os.unlink(temp_path)

    def test_file_not_found(self):
        tool = ResumeAnalyzerTool()
        result = tool.execute(file_path="/nonexistent/resume.txt")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("")
            temp_path = f.name

        try:
            tool = ResumeAnalyzerTool()
            result = tool.execute(file_path=temp_path)

            assert result["success"] is False
            assert "empty" in result["error"]
        finally:
            os.unlink(temp_path)


class TestSkillsMatcher:
    def test_perfect_match(self):
        tool = SkillsMatcherTool()
        result = tool.execute(
            required_skills=["Python", "Docker"],
            candidate_skills=["Python", "Docker", "Git"],
        )

        assert result["success"] is True
        assert result["required_match_pct"] == 100.0
        assert len(result["missing_required"]) == 0

    def test_partial_match(self):
        tool = SkillsMatcherTool()
        result = tool.execute(
            required_skills=["Python", "Go", "Rust"],
            candidate_skills=["Python"],
        )

        assert result["success"] is True
        assert result["required_match_pct"] < 100
        assert "Go" in result["missing_required"]
        assert "Rust" in result["missing_required"]

    def test_alias_matching(self):
        tool = SkillsMatcherTool()
        result = tool.execute(
            required_skills=["JS", "PostgreSQL"],
            candidate_skills=["JavaScript", "Postgres"],
        )

        assert result["success"] is True
        assert result["required_match_pct"] == 100.0

    def test_preferred_skills(self):
        tool = SkillsMatcherTool()
        result = tool.execute(
            required_skills=["Python"],
            candidate_skills=["Python"],
            preferred_skills=["Docker", "K8s"],
        )

        assert result["success"] is True
        assert len(result["matched_required"]) == 1
        assert len(result["missing_preferred"]) == 2

    def test_empty_skills(self):
        tool = SkillsMatcherTool()
        result = tool.execute(
            required_skills=[],
            candidate_skills=[],
        )

        assert result["success"] is True
        assert result["overall_match_pct"] == 0


class TestCoverLetter:
    def test_generate_letter(self):
        tool = CoverLetterTool()
        result = tool.execute(
            candidate_name="John Doe",
            company_name="Acme Corp",
            role_title="Software Engineer",
            matched_skills=["Python", "Docker", "PostgreSQL"],
            missing_skills=["Go"],
            key_experiences=[
                "Built data pipelines processing 1M+ records",
                "Led migration from monolith to microservices",
            ],
            company_context="building innovative developer tools",
        )

        assert result["success"] is True
        assert "John Doe" in result["cover_letter"]
        assert "Acme Corp" in result["cover_letter"]
        assert "Software Engineer" in result["cover_letter"]

    def test_letter_structure(self):
        tool = CoverLetterTool()
        result = tool.execute(
            candidate_name="Jane Smith",
            company_name="TechCo",
            role_title="Backend Engineer",
            matched_skills=["Python"],
            missing_skills=[],
            key_experiences=["Built REST APIs"],
        )

        assert "opening" in result["structure"]
        assert "closing" in result["structure"]
        assert result["stats"]["strengths_highlighted"] == 1

    def test_no_gaps(self):
        tool = CoverLetterTool()
        result = tool.execute(
            candidate_name="Jane Smith",
            company_name="TechCo",
            role_title="Engineer",
            matched_skills=["Python", "Go"],
            missing_skills=[],
            key_experiences=["Built systems"],
        )

        assert result["success"] is True
        # Growth narrative should be empty when no gaps
        assert result["structure"]["growth_narrative"] == ""
