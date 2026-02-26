import requests
from bs4 import BeautifulSoup
from typing import Any

from .base import Tool


class WebFetchTool(Tool):
    """Fetches and reads content from any URL.

    Use this when the user shares a link in chat — job postings,
    portfolios, articles, company pages, or any other URL.
    """

    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return (
            "Fetch and read content from any URL the user shares. "
            "Use this when the user pastes a link to a job posting, "
            "article, portfolio, company page, or any other webpage. "
            "Returns the page title, description, and main text content."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch (must start with http:// or https://)",
                },
            },
            "required": ["url"],
        }

    def _fetch_page(self, url: str) -> dict[str, str] | None:
        """Fetch a webpage and extract structured content."""
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

            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else ""

            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"]

            body_text = soup.get_text(separator="\n", strip=True)
            # Collapse excessive blank lines
            lines = [line for line in body_text.split("\n") if line.strip()]
            body_text = "\n".join(lines)

            return {
                "title": title,
                "description": meta_desc,
                "content": body_text[:6000],
            }
        except requests.RequestException:
            return None

    def execute(self, **kwargs) -> dict[str, Any]:
        url = kwargs["url"]

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        result = self._fetch_page(url)

        if result is None:
            return {
                "success": False,
                "error": f"Could not fetch content from: {url}",
            }

        return {
            "success": True,
            "url": url,
            "title": result["title"],
            "description": result["description"],
            "content": result["content"],
        }
