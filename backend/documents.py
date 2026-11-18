"""The policy wording and the claims manual, split into numbered sections."""

import re
from functools import cache
from typing import Literal

from backend.db import DATA_DIR

Document = Literal["policy_wording", "claims_manual"]

DOCUMENTS: dict[str, tuple[str, str]] = {
    "policy_wording": ("Policy wording", "policy_wording.md"),
    "claims_manual": ("Claims manual", "claims_manual.md"),
}

HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)


@cache
def sections(document: Document) -> list[dict[str, str | int]]:
    """Return a document's sections in order, each with its number, title and text."""
    text = (DATA_DIR / DOCUMENTS[document][1]).read_text(encoding="utf-8")
    headings = list(HEADING.finditer(text))
    ends = [heading.start() for heading in headings[1:]] + [len(text)]
    return [
        {
            "number": int(heading.group(1)),
            "title": heading.group(2),
            "text": text[heading.start() : end].strip(),
        }
        for heading, end in zip(headings, ends, strict=True)
    ]


def title(document: Document) -> str:
    return DOCUMENTS[document][0]
