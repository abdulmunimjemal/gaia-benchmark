from __future__ import annotations

import base64
import csv
import mimetypes
import re
import zipfile
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path

import pandas as pd
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader

from gaia_bot.models import ArtifactObservation, TaskRecord
from gaia_bot.settings import Settings

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".jsonl",
    ".csv",
    ".tsv",
    ".html",
    ".htm",
    ".xml",
    ".yaml",
    ".yml",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class TaskArtifactManager:
    def __init__(
        self,
        *,
        settings: Settings,
        task: TaskRecord,
        task_workspace: Path,
        anthropic_client: AsyncAnthropic,
    ) -> None:
        self.settings = settings
        self.task = task
        self.task_workspace = task_workspace
        self.anthropic = anthropic_client
        self.observations: list[ArtifactObservation] = []
        self.task_workspace.mkdir(parents=True, exist_ok=True)

    def resolve_task_attachment(self) -> Path | None:
        if self.task.attachment_path:
            path = Path(self.task.attachment_path)
            if not path.is_absolute() and self.task.dataset_root:
                path = Path(self.task.dataset_root) / path
            if path.exists():
                return path
        if self.task.attachment_name and self.task.dataset_root:
            candidate = Path(self.task.dataset_root) / self.task.attachment_name
            if candidate.exists():
                return candidate
        return None

    async def read_task_attachment(self) -> ArtifactObservation | None:
        path = self.resolve_task_attachment()
        if path is None:
            return None
        return await self.read_local_path(path, source_type="task_attachment")

    async def read_local_path(
        self,
        path: Path,
        *,
        source_type: str = "local_file",
    ) -> ArtifactObservation:
        kind, text = await self._extract_text(path)
        stored_path = self._persist_text(path.stem, text)
        observation = ArtifactObservation(
            name=path.name,
            source_type=source_type,  # type: ignore[arg-type]
            source_uri=str(path),
            kind=kind,
            stored_path=str(stored_path),
            excerpt=text[:600],
        )
        self.observations.append(observation)
        return observation

    async def persist_web_extract(
        self,
        url: str,
        text: str,
        *,
        kind: str = "web_text",
    ) -> ArtifactObservation:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")[:80] or "web"
        stored_path = self._persist_text(slug, text)
        observation = ArtifactObservation(
            name=slug,
            source_type="web_fetch",
            source_uri=url,
            kind=kind,
            stored_path=str(stored_path),
            excerpt=text[:600],
        )
        self.observations.append(observation)
        return observation

    async def _extract_text(self, path: Path) -> tuple[str, str]:
        suffix = path.suffix.lower()
        if suffix in {".csv", ".tsv"}:
            return "table", _extract_delimited(path, delimiter="," if suffix == ".csv" else "\t")
        if suffix == ".xlsx":
            return "spreadsheet", _extract_xlsx(path)
        if suffix == ".docx":
            return "document", _extract_docx(path)
        if suffix == ".pdf":
            return "pdf", _extract_pdf(path)
        if suffix == ".zip":
            return "archive", await self._extract_zip(path)
        if suffix in {".html", ".htm"}:
            return "html", _extract_html(path.read_text(errors="ignore"))
        if suffix in IMAGE_EXTENSIONS:
            return "image", await self._extract_image(path)
        if suffix in TEXT_EXTENSIONS or not suffix:
            return "text", path.read_text(errors="ignore")[: self.settings.max_fetch_chars]
        return "binary", f"Binary file: {path.name}"

    async def _extract_zip(self, path: Path) -> str:
        lines = [f"Archive: {path.name}"]
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            lines.append("Entries:")
            lines.extend(f"- {name}" for name in names[:20])
            for name in names[:3]:
                suffix = Path(name).suffix.lower()
                if suffix not in TEXT_EXTENSIONS | {".pdf"}:
                    continue
                with archive.open(name) as handle:
                    data = handle.read()
                extracted = await self._extract_bytes(name, data)
                lines.append(f"\n--- {name} ---\n{extracted[:1200]}")
        return "\n".join(lines)[: self.settings.max_fetch_chars]

    async def _extract_image(self, path: Path) -> str:
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        response = await self.anthropic.messages.create(
            model=self.settings.anthropic_model_judge,
            max_tokens=800,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract all visible text and the key factual details "
                                "from this image. "
                                "Return plain text only."
                            ),
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": data,
                            },
                        },
                    ],
                }
            ],
        )
        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        return text.strip()

    async def _extract_bytes(self, name: str, data: bytes) -> str:
        suffix = Path(name).suffix.lower()
        if suffix == ".pdf":
            return _extract_pdf(BytesIO(data))
        if suffix in {".html", ".htm"}:
            return _extract_html(data.decode(errors="ignore"))
        if suffix in {".csv", ".tsv"}:
            text = data.decode(errors="ignore")
            delimiter = "," if suffix == ".csv" else "\t"
            return _extract_delimited_from_text(text, delimiter)
        return data.decode(errors="ignore")

    def _persist_text(self, stem: str, text: str) -> Path:
        safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("_")[:80] or "artifact"
        destination = self.task_workspace / f"{safe_stem}.txt"
        destination.write_text(text[: self.settings.max_fetch_chars])
        return destination


def _extract_pdf(path_or_buffer: Path | BytesIO) -> str:
    reader = PdfReader(path_or_buffer)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(path: Path) -> str:
    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _extract_html(text: str) -> str:
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    body = soup.get_text(" ", strip=True)
    return f"Title: {title}\n\n{body}".strip()


def _extract_xlsx(path: Path) -> str:
    sheets = pd.read_excel(path, sheet_name=None)
    lines: list[str] = []
    for sheet_name, frame in list(sheets.items())[:5]:
        lines.append(f"Sheet: {sheet_name}")
        lines.append(frame.head(10).to_csv(index=False))
    return "\n".join(lines)


def _extract_delimited(path: Path, *, delimiter: str) -> str:
    return _extract_delimited_from_text(path.read_text(errors="ignore"), delimiter)


def _extract_delimited_from_text(text: str, delimiter: str) -> str:
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    rows = list(_take(reader, 12))
    return "\n".join(delimiter.join(cell for cell in row) for row in rows)


def _take(items: Iterable[list[str]], count: int) -> list[list[str]]:
    output: list[list[str]] = []
    for item in items:
        output.append(item)
        if len(output) >= count:
            break
    return output
