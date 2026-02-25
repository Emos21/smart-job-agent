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
from .tools.job_search import JobSearchTool


def build_agent(provider: str = "groq", model: str | None = None) -> Agent:
    """Wire up all tools and create an agent instance."""
    registry = ToolRegistry()
    registry.register(JDParserTool())
    registry.register(ResumeAnalyzerTool())
    registry.register(SkillsMatcherTool())
    registry.register(CompanyResearcherTool())
    registry.register(CoverLetterTool())
    registry.register(JobSearchTool())
    return Agent(registry=registry, provider=provider, model=model)


@click.group()
def cli():
    """KaziAI — AI-powered career platform."""
    pass


@cli.command()
@click.option("--jd", required=True, help="Path to job description text file or URL")
@click.option("--resume", required=True, help="Path to resume text file")
@click.option("--url", is_flag=True, default=False, help="Treat --jd as a URL to fetch")
@click.option(
    "--provider",
    default="groq",
    type=click.Choice(["groq", "openai", "deepseek"]),
    help="LLM provider (default: groq)",
)
@click.option("--model", default=None, help="Override the default model for the provider")
def analyze(jd: str, resume: str, url: bool, provider: str, model: str):
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

    env_key = Agent.PROVIDERS[provider]["env_key"]
    if not os.getenv(env_key):
        click.echo(
            f"Error: {env_key} not set. "
            f"Copy .env.example to .env and add your key.",
            err=True,
        )
        sys.exit(1)

    # If JD is a file path, read its contents
    if not url:
        with open(jd, "r") as f:
            jd_content = f.read()
    else:
        jd_content = jd

    agent = build_agent(provider=provider, model=model)

    click.echo("=" * 60)
    click.echo("KAZI AI")
    click.echo(f"Provider: {provider} | Model: {agent.model}")
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
@click.option("--keywords", required=True, help="Comma-separated search keywords (e.g. 'python,backend,ai')")
@click.option("--max-results", default=10, help="Max jobs to return (default: 10)")
def search(keywords: str, max_results: int):
    """Search for jobs matching your skills.

    Searches across multiple free job boards (RemoteOK, Arbeitnow)
    without requiring any API keys.
    """
    keyword_list = [k.strip() for k in keywords.split(",")]

    click.echo("=" * 60)
    click.echo("JOB SEARCH")
    click.echo(f"Keywords: {', '.join(keyword_list)}")
    click.echo("=" * 60)

    tool = JobSearchTool()
    result = tool.execute(keywords=keyword_list, max_results=max_results)

    if not result["jobs"]:
        click.echo("\nNo matching jobs found. Try broader keywords.")
        return

    click.echo(f"\nFound {result['total_found']} jobs, showing {result['returned']}:\n")

    for i, job in enumerate(result["jobs"], 1):
        click.echo(f"  {i}. {job['title']}")
        click.echo(f"     Company:  {job['company']}")
        click.echo(f"     Location: {job['location']}")
        if job.get("tags"):
            click.echo(f"     Tags:     {', '.join(job['tags'][:6])}")
        if job.get("salary_min") and job.get("salary_max"):
            click.echo(f"     Salary:   ${job['salary_min']:,} - ${job['salary_max']:,}")
        click.echo(f"     Source:   {job['source']}")
        if job.get("url"):
            click.echo(f"     URL:      {job['url']}")
        click.echo()


@cli.command()
def tools():
    """List all available agent tools."""
    registry = ToolRegistry()
    registry.register(JDParserTool())
    registry.register(ResumeAnalyzerTool())
    registry.register(SkillsMatcherTool())
    registry.register(CompanyResearcherTool())
    registry.register(CoverLetterTool())
    registry.register(JobSearchTool())

    click.echo("Available tools:\n")
    for tool in registry.list_tools():
        click.echo(f"  {tool.name}")
        click.echo(f"    {tool.description}")
        click.echo()


def main():
    cli()


if __name__ == "__main__":
    main()
