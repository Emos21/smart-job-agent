from typing import Any

from .base import Tool


class LearningPathTool(Tool):
    """Generates a structured learning path based on skill gaps.

    Takes the skill gaps identified during job analysis and creates
    a prioritized study plan with specific resources, timeframes,
    and milestones to help the candidate become competitive.
    """

    # Resource categories mapped to common tech skills
    RESOURCE_MAP = {
        "python": {
            "beginner": ["Python official tutorial (docs.python.org)", "Automate the Boring Stuff (free online)"],
            "intermediate": ["Fluent Python by Luciano Ramalho", "Python Cookbook by David Beazley"],
            "advanced": ["CPython internals", "Build projects: CLI tools, web scrapers, API servers"],
        },
        "javascript": {
            "beginner": ["MDN JavaScript Guide", "JavaScript.info"],
            "intermediate": ["You Don't Know JS series (free on GitHub)", "Eloquent JavaScript"],
            "advanced": ["Build a framework from scratch", "Contribute to open source JS projects"],
        },
        "react": {
            "beginner": ["Official React docs (react.dev)", "React Tutorial for Beginners (Scrimba, free)"],
            "intermediate": ["Build 3-5 projects with hooks, context, routing", "React Patterns by Kent C. Dodds"],
            "advanced": ["Build a component library", "Study React source code", "Performance optimization"],
        },
        "typescript": {
            "beginner": ["TypeScript Handbook (typescriptlang.org)", "Matt Pocock's Total TypeScript (free tier)"],
            "intermediate": ["Type challenges (github.com/type-challenges)", "Migrate a JS project to TS"],
            "advanced": ["Build generic utility types", "Advanced type inference patterns"],
        },
        "sql": {
            "beginner": ["SQLBolt interactive tutorial", "W3Schools SQL Tutorial"],
            "intermediate": ["PostgreSQL exercises (pgexercises.com)", "Database design and normalization"],
            "advanced": ["Query optimization and EXPLAIN plans", "Build a data pipeline"],
        },
        "docker": {
            "beginner": ["Docker Getting Started (docs.docker.com)", "Play with Docker (online sandbox)"],
            "intermediate": ["Docker Compose multi-service apps", "Dockerfile best practices"],
            "advanced": ["Multi-stage builds", "Container orchestration with Kubernetes"],
        },
        "kubernetes": {
            "beginner": ["Kubernetes official tutorials", "Minikube local setup"],
            "intermediate": ["Deploy a multi-service app on K8s", "Helm charts"],
            "advanced": ["Custom operators", "Service mesh (Istio/Linkerd)"],
        },
        "aws": {
            "beginner": ["AWS Free Tier exploration", "AWS Cloud Practitioner path"],
            "intermediate": ["AWS Solutions Architect Associate prep", "Build serverless apps (Lambda + API Gateway)"],
            "advanced": ["Infrastructure as Code (CDK/Terraform)", "Multi-region architectures"],
        },
        "machine learning": {
            "beginner": ["Andrew Ng's ML Specialization (Coursera)", "Fast.ai Practical Deep Learning"],
            "intermediate": ["Kaggle competitions", "Build end-to-end ML pipeline"],
            "advanced": ["ML system design", "MLOps and model deployment"],
        },
        "system design": {
            "beginner": ["System Design Primer (GitHub)", "Grokking System Design (Educative)"],
            "intermediate": ["Design real systems (URL shortener, chat app, etc.)", "Read engineering blogs"],
            "advanced": ["Distributed systems papers", "Design systems at scale"],
        },
    }

    @property
    def name(self) -> str:
        return "generate_learning_path"

    @property
    def description(self) -> str:
        return (
            "Generate a structured learning path based on skill gaps. "
            "Creates a prioritized study plan with specific resources, "
            "estimated timeframes, and milestones for each missing skill."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "missing_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills the candidate needs to learn (from gap analysis)",
                },
                "current_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skills the candidate already has (for context)",
                    "default": [],
                },
                "target_role": {
                    "type": "string",
                    "description": "The role the candidate is targeting",
                    "default": "",
                },
                "available_hours_per_week": {
                    "type": "integer",
                    "description": "Hours per week available for learning",
                    "default": 10,
                },
            },
            "required": ["missing_skills"],
        }

    def _determine_level(self, skill: str, current_skills: list[str]) -> str:
        """Determine what level to start at based on related skills."""
        skill_lower = skill.lower()
        current_lower = [s.lower() for s in current_skills]

        # If they know related technologies, they can start at intermediate
        related_groups = [
            {"python", "django", "flask", "fastapi"},
            {"javascript", "typescript", "react", "vue", "angular", "node"},
            {"java", "spring", "kotlin"},
            {"aws", "gcp", "azure", "cloud"},
            {"docker", "kubernetes", "devops"},
            {"sql", "postgresql", "mysql", "mongodb", "database"},
            {"machine learning", "deep learning", "ai", "tensorflow", "pytorch"},
        ]

        for group in related_groups:
            if skill_lower in group:
                overlap = group.intersection(set(current_lower))
                if overlap:
                    return "intermediate"

        return "beginner"

    def _get_resources(self, skill: str, level: str) -> list[str]:
        """Get learning resources for a skill at a given level."""
        skill_lower = skill.lower()

        # Try exact match first
        if skill_lower in self.RESOURCE_MAP:
            return self.RESOURCE_MAP[skill_lower].get(level, [])

        # Try partial match
        for key, resources in self.RESOURCE_MAP.items():
            if key in skill_lower or skill_lower in key:
                return resources.get(level, [])

        # Generic resources
        return [
            f"Search '{skill} tutorial' on YouTube or Coursera",
            f"Read official {skill} documentation",
            f"Build a small project using {skill}",
        ]

    def _estimate_time(self, skill: str, level: str) -> dict[str, Any]:
        """Estimate learning time based on skill complexity and starting level."""
        # Base hours by complexity
        complex_skills = {
            "kubernetes", "system design", "machine learning", "deep learning",
            "distributed systems", "aws", "gcp", "azure",
        }
        moderate_skills = {
            "react", "typescript", "docker", "sql", "graphql", "redux",
            "python", "java", "go", "rust",
        }

        skill_lower = skill.lower()
        if any(cs in skill_lower for cs in complex_skills):
            base_hours = {"beginner": 80, "intermediate": 50, "advanced": 100}
        elif any(ms in skill_lower for ms in moderate_skills):
            base_hours = {"beginner": 40, "intermediate": 25, "advanced": 60}
        else:
            base_hours = {"beginner": 20, "intermediate": 15, "advanced": 40}

        hours = base_hours.get(level, 30)
        return {"estimated_hours": hours, "starting_level": level}

    def execute(self, **kwargs) -> dict[str, Any]:
        missing_skills = kwargs["missing_skills"]
        current_skills = kwargs.get("current_skills", [])
        target_role = kwargs.get("target_role", "")
        hours_per_week = kwargs.get("available_hours_per_week", 10)

        learning_paths = []
        total_hours = 0

        # Prioritize: required skills first, sorted by estimated learning time
        for priority, skill in enumerate(missing_skills, 1):
            level = self._determine_level(skill, current_skills)
            resources = self._get_resources(skill, level)
            time_est = self._estimate_time(skill, level)
            weeks = max(1, round(time_est["estimated_hours"] / hours_per_week))

            total_hours += time_est["estimated_hours"]

            learning_paths.append({
                "priority": priority,
                "skill": skill,
                "starting_level": level,
                "estimated_hours": time_est["estimated_hours"],
                "estimated_weeks": weeks,
                "resources": resources,
                "milestones": [
                    f"Complete introductory material for {skill}",
                    f"Build a small project using {skill}",
                    f"Apply {skill} in a portfolio project or contribution",
                ],
            })

        total_weeks = max(1, round(total_hours / hours_per_week))

        return {
            "success": True,
            "target_role": target_role,
            "total_skills_to_learn": len(learning_paths),
            "total_estimated_hours": total_hours,
            "total_estimated_weeks": total_weeks,
            "hours_per_week": hours_per_week,
            "learning_paths": learning_paths,
        }
