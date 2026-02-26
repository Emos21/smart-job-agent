import requests
from typing import Any

from .base import Tool


class SalaryResearchTool(Tool):
    """Researches salary ranges for a given role and location.

    Pulls real salary data from job postings that include compensation.
    Searches free job APIs and aggregates salary ranges to give
    market-rate estimates for a given role.
    """

    @property
    def name(self) -> str:
        return "research_salary"

    @property
    def description(self) -> str:
        return (
            "Research market salary data for a specific role, location, and "
            "experience level. Pulls from job boards with salary information "
            "to estimate competitive compensation ranges."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "role_title": {
                    "type": "string",
                    "description": "The job title to research (e.g., 'Senior Backend Engineer')",
                },
                "location": {
                    "type": "string",
                    "description": "Target location or 'remote' (e.g., 'San Francisco', 'remote')",
                    "default": "remote",
                },
                "experience_level": {
                    "type": "string",
                    "description": "Experience level: junior, mid, senior, lead",
                    "default": "mid",
                },
            },
            "required": ["role_title"],
        }

    def _search_remoteok_salaries(self, keywords: list[str]) -> list[dict]:
        """Search RemoteOK for jobs with salary data."""
        try:
            headers = {"User-Agent": "KaziAI/1.0"}
            response = requests.get(
                "https://remoteok.com/api",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            jobs = data[1:] if len(data) > 1 else []

            results = []
            keywords_lower = [k.lower() for k in keywords]

            for job in jobs:
                salary_min = job.get("salary_min")
                salary_max = job.get("salary_max")
                if not salary_min and not salary_max:
                    continue

                position = job.get("position", "").lower()
                tags = [t.lower() for t in job.get("tags", [])]
                searchable = f"{position} {' '.join(tags)}"

                if any(kw in searchable for kw in keywords_lower):
                    results.append({
                        "title": job.get("position", ""),
                        "company": job.get("company", ""),
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "location": "Remote",
                        "source": "RemoteOK",
                    })

            return results
        except requests.RequestException:
            return []

    def _search_arbeitnow_salaries(self, keywords: list[str]) -> list[dict]:
        """Search Arbeitnow for jobs with salary data."""
        try:
            search_query = "+".join(keywords)
            response = requests.get(
                "https://www.arbeitnow.com/api/job-board-api",
                params={"search": search_query},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            jobs = data.get("data", [])

            results = []
            for job in jobs:
                # Arbeitnow doesn't always include salary, but some do
                title = job.get("title", "")
                location = job.get("location", "")
                results.append({
                    "title": title,
                    "company": job.get("company_name", ""),
                    "salary_min": None,
                    "salary_max": None,
                    "location": location,
                    "source": "Arbeitnow",
                })

            return results
        except requests.RequestException:
            return []

    def _estimate_range(
        self, salary_data: list[dict], experience_level: str
    ) -> dict[str, Any]:
        """Estimate salary range from collected data points."""
        # Extract valid salary values
        mins = [s["salary_min"] for s in salary_data if s.get("salary_min")]
        maxs = [s["salary_max"] for s in salary_data if s.get("salary_max")]
        all_values = mins + maxs

        if not all_values:
            return {
                "estimated_min": None,
                "estimated_max": None,
                "data_points": 0,
                "confidence": "low",
            }

        # Experience level multipliers
        multipliers = {
            "junior": 0.75,
            "mid": 1.0,
            "senior": 1.25,
            "lead": 1.45,
        }
        mult = multipliers.get(experience_level, 1.0)

        avg_min = sum(mins) / len(mins) if mins else min(all_values)
        avg_max = sum(maxs) / len(maxs) if maxs else max(all_values)

        # Apply experience adjustment
        est_min = round(avg_min * mult / 1000) * 1000
        est_max = round(avg_max * mult / 1000) * 1000

        data_points = len(salary_data)
        confidence = "high" if data_points >= 10 else "medium" if data_points >= 3 else "low"

        return {
            "estimated_min": est_min,
            "estimated_max": est_max,
            "data_points": data_points,
            "confidence": confidence,
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        role = kwargs["role_title"]
        location = kwargs.get("location", "remote")
        experience = kwargs.get("experience_level", "mid")

        # Extract search keywords from role title
        keywords = [w for w in role.split() if len(w) > 2]

        # Search multiple sources
        salary_data = []
        salary_data.extend(self._search_remoteok_salaries(keywords))
        salary_data.extend(self._search_arbeitnow_salaries(keywords))

        # Filter to jobs with salary info
        with_salary = [s for s in salary_data if s.get("salary_min") or s.get("salary_max")]

        estimate = self._estimate_range(with_salary, experience)

        # Sample postings for context
        sample_postings = [
            {
                "title": s["title"],
                "company": s["company"],
                "salary_range": f"${s['salary_min']:,} - ${s['salary_max']:,}"
                if s.get("salary_min") and s.get("salary_max")
                else "Salary not disclosed",
                "location": s["location"],
            }
            for s in salary_data[:10]
        ]

        return {
            "success": True,
            "role": role,
            "location": location,
            "experience_level": experience,
            "estimate": estimate,
            "sample_postings": sample_postings,
            "total_postings_found": len(salary_data),
            "postings_with_salary": len(with_salary),
        }
