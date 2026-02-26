import requests
from typing import Any

from .base import Tool


class GitHubAnalyzerTool(Tool):
    """Analyzes a GitHub profile to extract demonstrable skills.

    Scans public repositories to identify programming languages,
    frameworks, contribution patterns, and project complexity.
    Uses the GitHub public API (no auth needed for public profiles).
    """

    # Map common repo topics/languages to skill categories
    FRAMEWORK_INDICATORS = {
        "react": "React",
        "next": "Next.js",
        "vue": "Vue.js",
        "angular": "Angular",
        "svelte": "Svelte",
        "django": "Django",
        "flask": "Flask",
        "fastapi": "FastAPI",
        "express": "Express.js",
        "nestjs": "NestJS",
        "spring": "Spring Boot",
        "rails": "Ruby on Rails",
        "laravel": "Laravel",
        "tensorflow": "TensorFlow",
        "pytorch": "PyTorch",
        "langchain": "LangChain",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "terraform": "Terraform",
        "prisma": "Prisma",
        "tailwind": "Tailwind CSS",
        "graphql": "GraphQL",
    }

    @property
    def name(self) -> str:
        return "analyze_github"

    @property
    def description(self) -> str:
        return (
            "Analyze a GitHub profile to extract demonstrable skills. "
            "Scans public repositories to identify programming languages, "
            "frameworks, contribution activity, and project complexity. "
            "Useful for strengthening a resume with verified technical skills."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "GitHub username to analyze",
                },
                "max_repos": {
                    "type": "integer",
                    "description": "Maximum number of repos to analyze",
                    "default": 20,
                },
            },
            "required": ["username"],
        }

    def _fetch_repos(self, username: str, max_repos: int) -> list[dict]:
        """Fetch public repos for a user."""
        try:
            headers = {"Accept": "application/vnd.github.v3+json"}
            response = requests.get(
                f"https://api.github.com/users/{username}/repos",
                headers=headers,
                params={
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": min(max_repos, 100),
                    "type": "owner",
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return []

    def _fetch_languages(self, username: str, repo_name: str) -> dict:
        """Fetch language breakdown for a repo."""
        try:
            response = requests.get(
                f"https://api.github.com/repos/{username}/{repo_name}/languages",
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=5,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return {}

    def _detect_frameworks(self, repo: dict) -> list[str]:
        """Detect frameworks from repo name, description, and topics."""
        frameworks = []
        searchable = " ".join([
            repo.get("name", ""),
            repo.get("description", "") or "",
            " ".join(repo.get("topics", [])),
        ]).lower()

        for indicator, framework in self.FRAMEWORK_INDICATORS.items():
            if indicator in searchable:
                frameworks.append(framework)

        return frameworks

    def execute(self, **kwargs) -> dict[str, Any]:
        username = kwargs["username"]
        max_repos = kwargs.get("max_repos", 20)

        repos = self._fetch_repos(username, max_repos)
        if not repos:
            return {
                "success": False,
                "error": f"Could not fetch repos for '{username}'. Check if the username exists and has public repos.",
            }

        # Aggregate language stats
        all_languages: dict[str, int] = {}
        all_frameworks: set[str] = set()
        repo_summaries = []
        total_stars = 0
        total_forks = 0

        for repo in repos:
            if repo.get("fork"):
                continue  # Skip forks

            # Get languages for this repo
            languages = self._fetch_languages(username, repo["name"])
            for lang, bytes_count in languages.items():
                all_languages[lang] = all_languages.get(lang, 0) + bytes_count

            # Detect frameworks
            frameworks = self._detect_frameworks(repo)
            all_frameworks.update(frameworks)

            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)
            total_stars += stars
            total_forks += forks

            repo_summaries.append({
                "name": repo["name"],
                "description": repo.get("description", "") or "No description",
                "languages": list(languages.keys()),
                "frameworks": frameworks,
                "stars": stars,
                "forks": forks,
                "updated": repo.get("updated_at", ""),
            })

        # Sort languages by usage
        sorted_languages = sorted(
            all_languages.items(), key=lambda x: x[1], reverse=True
        )
        total_bytes = sum(b for _, b in sorted_languages)
        language_breakdown = [
            {
                "language": lang,
                "percentage": round(bytes_count / total_bytes * 100, 1) if total_bytes > 0 else 0,
            }
            for lang, bytes_count in sorted_languages[:10]
        ]

        # Sort repos by stars
        top_repos = sorted(repo_summaries, key=lambda r: r["stars"], reverse=True)[:5]

        return {
            "success": True,
            "username": username,
            "total_repos": len(repo_summaries),
            "total_stars": total_stars,
            "total_forks": total_forks,
            "primary_languages": language_breakdown,
            "frameworks_detected": sorted(all_frameworks),
            "top_repos": top_repos,
            "all_repos": repo_summaries,
        }
