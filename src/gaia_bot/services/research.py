from __future__ import annotations

import asyncio
from io import BytesIO
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from pypdf import PdfReader

from gaia_bot.config.settings import Settings
from gaia_bot.contracts.basemodels import SearchHit


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

        hits = await asyncio.to_thread(_run)
        deduped: list[SearchHit] = []
        seen: set[str] = set()
        for hit in sorted(hits, key=_search_priority):
            if not hit.url or hit.url in seen:
                continue
            seen.add(hit.url)
            deduped.append(hit)
        return deduped[:limit]

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
        is_pdf = "application/pdf" in content_type or response.content.lstrip().startswith(b"%PDF-")
        if is_pdf:
            try:
                reader = PdfReader(BytesIO(response.content))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                if text.strip():
                    return text[:limit]
            except Exception:
                pass

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        body = soup.get_text(" ", strip=True)
        text = f"Title: {title}\n\n{body}".strip()
        return text[:limit]


def _search_priority(hit: SearchHit) -> tuple[int, str]:
    host = urlparse(hit.url).netloc.lower()
    preferred_hosts = (
        "wikipedia.org",
        ".gov",
        ".edu",
        "nih.gov",
        "ncbi.nlm.nih.gov",
        "archive.org",
        "books.google.",
        "library.oapen.org",
        "projectmuse.jhu.edu",
    )
    weak_hosts = (
        "goldderby.com",
        "purewow.com",
        "yahoo.com",
        "jsonline.com",
        "everybodywiki.com",
        "fandom.com",
    )
    if any(token in host for token in preferred_hosts):
        return (0, host)
    if any(token in host for token in weak_hosts):
        return (2, host)
    return (1, host)


__all__ = ["WebResearchClient"]
