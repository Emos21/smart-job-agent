import os
import sys

import click

from .agent import Agent
from .tools.base import ToolRegistry
from .tools.jd_parser import JDParserTool
from .tools.resume_analyzer import ResumeAnalyzerTool
from .tools.skills_matcher import SkillsMatcherTool
from .tools.company_researcher import CompanyResearcherTool
from .tools.cover_letter import CoverLetterTool


def build_agent(model: str = "gpt-4o-mini") -> Agent:
    """Wire up all tools and create an agent instance."""
    registry = ToolRegistry()
    registry.register(JDParserTool())
    registry.register(ResumeAnalyzerTool())
    registry.register(SkillsMatcherTool())
    registry.register(CompanyResearcherTool())
    registry.register(CoverLetterTool())
    return Agent(registry=registry, model=model)


@click.group()
def cli():
    """Smart Job Agent — AI-powered job application analyzer."""
    pass


@cli.command()
@click.option("--jd", required=True, help="Path to job description text file or URL")
@click.option("--resume", required=True, help="Path to resume text file")
@click.option("--url", is_flag=True, default=False, help="Treat --jd as a URL to fetch")
@click.option(
    "--model",
    default="gpt-4o-mini",
    help="OpenAI model to use (default: gpt-4o-mini)",
)
def analyze(jd: str, resume: str, url: bool, model: str):
    """Analyze a job description against your resume.

    The agent autonomously parses the JD, analyzes your resume,
    matches skills, researches the company, and generates
    tailored application materials.
    """
    # Validate inputs
    if not url and not os.path.exists(jd):
        click.echo(f"Error: JD file not found: {jd}", err=True)
        sys.exit(1)

    if not os.path.exists(resume):
        click.echo(f"Error: Resume file not found: {resume}", err=True)
        sys.exit(1)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        click.echo(
            "Error: OPENAI_API_KEY not set. "
            "Copy .env.example to .env and add your key.",
            err=True,
        )
        sys.exit(1)

    # If JD is a file path, read its contents
    if not url:
        with open(jd, "r") as f:
            jd_content = f.read()
    else:
        jd_content = jd

    agent = build_agent(model=model)

    click.echo("=" * 60)
    click.echo("SMART JOB AGENT")
    click.echo("=" * 60)

    result = agent.run(
        jd_source=jd_content,
        resume_path=resume,
        is_url=url,
    )

    click.echo("\n" + "=" * 60)
    click.echo("ANALYSIS RESULTS")
    click.echo("=" * 60)
    click.echo(result)


@cli.command()
def tools():
    """List all available agent tools."""
    registry = ToolRegistry()
    registry.register(JDParserTool())
    registry.register(ResumeAnalyzerTool())
    registry.register(SkillsMatcherTool())
    registry.register(CompanyResearcherTool())
    registry.register(CoverLetterTool())

    click.echo("Available tools:\n")
    for tool in registry.list_tools():
        click.echo(f"  {tool.name}")
        click.echo(f"    {tool.description}")
        click.echo()


def main():
    cli()


if __name__ == "__main__":
    main()
