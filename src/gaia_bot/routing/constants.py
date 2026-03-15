from __future__ import annotations

import re

DIRECT_PATTERNS = [
    re.compile(r"^\s*what is\s+\d+\s*[-+*/]\s*\d+\??\s*$", re.IGNORECASE),
    re.compile(r"^\s*what is the capital of ", re.IGNORECASE),
    re.compile(r"^\s*what day comes after ", re.IGNORECASE),
]

CODE_HINTS = (
    "calculate",
    "calculation",
    "compute",
    "average",
    "count",
    "unique",
    "sum",
    "difference",
    "how many more",
    "compared to",
    "compare",
    "ratio",
    "convert",
    "distance",
    "geographical distance",
    "furthest",
    "westernmost",
    "easternmost",
    "pace",
    "speed",
    "time would it take",
    "as of",
    "prior to",
    "before",
    "for each day",
    "times was",
    "round your result",
    "spreadsheet",
    "csv",
    "tsv",
    "xlsx",
    "excel",
)

WEB_HINTS = (
    "website",
    "official",
    "current",
    "latest",
    "today",
    "article",
    "published",
    "url",
    "wikipedia",
    "history",
    "version",
    "news",
)

WIKIPEDIA_PAGE_RE = re.compile(
    r"wikipedia page for ([A-Za-z0-9'()/ -]+)",
    re.IGNORECASE,
)

__all__ = ["CODE_HINTS", "DIRECT_PATTERNS", "WEB_HINTS", "WIKIPEDIA_PAGE_RE"]
