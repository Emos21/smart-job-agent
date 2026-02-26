import requests
from typing import Any

from .base import Tool


class JobSearchTool(Tool):
    """Searches for remote tech jobs matching given criteria.

    Queries multiple free job APIs (RemoteOK, Arbeitnow) without
    requiring authentication. Returns matching positions with
    company, tags, and application URLs.
    """

    SOURCES = {
        "remoteok": {
            "url": "https://remoteok.com/api",
            "name": "RemoteOK",
        },
        "arbeitnow": {
            "url": "https://www.arbeitnow.com/api/job-board-api",
            "name": "Arbeitnow",
        },
    }

    @property
    def name(self) -> str:
        return "search_jobs"

    @property
    def description(self) -> str:
        return (
            "Search for jobs matching given keywords and skills. "
            "Use when user wants to find job openings, asks about available "
            "positions, or wants to explore the job market. "
            "Returns titles, companies, tags, and application URLs from multiple job boards."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Search keywords — role titles, skills, or technologies "
                        "(e.g. ['python', 'backend', 'ai engineer'])"
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 10,
                },
            },
            "required": ["keywords"],
        }

    def _search_remoteok(self, keywords: list[str]) -> list[dict]:
        """Search RemoteOK for matching jobs."""
        try:
            headers = {"User-Agent": "SmartJobAgent/1.0"}
            response = requests.get(
                self.SOURCES["remoteok"]["url"],
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            # First item is metadata, skip it
            jobs = data[1:] if len(data) > 1 else []

            # Filter by keywords
            matched = []
            keywords_lower = [k.lower() for k in keywords]

            for job in jobs:
                position = job.get("position", "").lower()
                tags = [t.lower() for t in job.get("tags", [])]
                company = job.get("company", "").lower()
                description = job.get("description", "").lower()

                searchable = f"{position} {' '.join(tags)} {company} {description}"

                if any(kw in searchable for kw in keywords_lower):
                    matched.append({
                        "title": job.get("position", ""),
                        "company": job.get("company", ""),
                        "location": "Remote",
                        "tags": job.get("tags", []),
                        "url": job.get("url", ""),
                        "date": job.get("date", ""),
                        "source": "RemoteOK",
                        "salary_min": job.get("salary_min"),
                        "salary_max": job.get("salary_max"),
                    })

            return matched
        except requests.RequestException:
            return []

    def _search_arbeitnow(self, keywords: list[str]) -> list[dict]:
        """Search Arbeitnow for matching jobs."""
        try:
            search_query = "+".join(keywords)
            response = requests.get(
                self.SOURCES["arbeitnow"]["url"],
                params={"search": search_query},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            jobs = data.get("data", [])
            matched = []
            keywords_lower = [k.lower() for k in keywords]

            for job in jobs:
                title = job.get("title", "").lower()
                description = job.get("description", "").lower()
                tags = [t.lower() for t in job.get("tags", [])]

                searchable = f"{title} {' '.join(tags)} {description}"

                if any(kw in searchable for kw in keywords_lower):
                    matched.append({
                        "title": job.get("title", ""),
                        "company": job.get("company_name", ""),
                        "location": job.get("location", ""),
                        "tags": job.get("tags", []),
                        "url": job.get("url", ""),
                        "date": job.get("created_at", ""),
                        "source": "Arbeitnow",
                        "remote": job.get("remote", False),
                    })

            return matched
        except requests.RequestException:
            return []

    def execute(self, **kwargs) -> dict[str, Any]:
        keywords = kwargs["keywords"]
        max_results = kwargs.get("max_results", 10)

        all_jobs = []

        # Search all sources
        all_jobs.extend(self._search_remoteok(keywords))
        all_jobs.extend(self._search_arbeitnow(keywords))

        # Deduplicate by title + company
        seen = set()
        unique_jobs = []
        for job in all_jobs:
            key = f"{job['title'].lower()}|{job['company'].lower()}"
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)

        # Limit results
        results = unique_jobs[:max_results]

        return {
            "success": True,
            "total_found": len(unique_jobs),
            "returned": len(results),
            "jobs": results,
            "sources_searched": list(self.SOURCES.keys()),
        }
