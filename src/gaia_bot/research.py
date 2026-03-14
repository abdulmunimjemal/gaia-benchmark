from __future__ import annotations

import asyncio
from io import BytesIO

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from pypdf import PdfReader

from gaia_bot.models import SearchHit
from gaia_bot.settings import Settings


class WebResearchClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search(self, query: str, max_results: int | None = None) -> list[SearchHit]:
        limit = max_results or self.settings.max_search_results

        def _run() -> list[SearchHit]:
            with DDGS() as ddgs:
                matches = ddgs.text(query, max_results=limit)
                return [
                    SearchHit(
                        title=item.get("title", ""),
                        url=item.get("href", ""),
                        snippet=item.get("body", ""),
                    )
                    for item in matches
                ]

        return await asyncio.to_thread(_run)

    async def fetch(self, url: str, max_chars: int | None = None) -> str:
        limit = max_chars or self.settings.max_fetch_chars
        timeout = httpx.Timeout(self.settings.http_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "gaia-bot/0.1 (+https://github.com/)"},
            )
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            reader = PdfReader(BytesIO(response.content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text[:limit]

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        body = soup.get_text(" ", strip=True)
        text = f"Title: {title}\n\n{body}".strip()
        return text[:limit]
