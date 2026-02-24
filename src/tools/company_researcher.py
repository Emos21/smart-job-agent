import requests
from bs4 import BeautifulSoup
from typing import Any

from .base import Tool


class CompanyResearcherTool(Tool):
    """Researches a company by fetching its website.

    Given a company name or URL, fetches public information
    to help the candidate understand the company before
    an interview.
    """

    @property
    def name(self) -> str:
        return "research_company"

    @property
    def description(self) -> str:
        return (
            "Research a company by fetching its website content. "
            "Provide a company name or URL to get an overview of "
            "what the company does, its mission, and key details."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Company name or website URL to research",
                },
            },
            "required": ["query"],
        }

    def _build_url(self, query: str) -> str:
        """Turn a company name or URL into a fetchable URL."""
        if query.startswith("http://") or query.startswith("https://"):
            return query
        # Try constructing a URL from the company name
        clean = query.lower().replace(" ", "").replace(",", "").replace(".", "")
        return f"https://www.{clean}.com"

    def _fetch_page(self, url: str) -> str | None:
        """Fetch a webpage and extract its text content."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            # Try to get meta description
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"]

            title = soup.title.string if soup.title else ""
            body_text = soup.get_text(separator="\n", strip=True)

            return f"Title: {title}\nDescription: {meta_desc}\n\n{body_text[:5000]}"
        except requests.RequestException:
            return None

    def execute(self, **kwargs) -> dict[str, Any]:
        query = kwargs["query"]
        url = self._build_url(query)

        content = self._fetch_page(url)

        if content is None:
            # Try with just the query as-is if URL construction failed
            if not query.startswith("http"):
                alt_url = f"https://{query}"
                content = self._fetch_page(alt_url)

        if content is None:
            return {
                "success": False,
                "error": f"Could not fetch company information for: {query}",
                "attempted_url": url,
            }

        return {
            "success": True,
            "url": url,
            "content": content,
        }
