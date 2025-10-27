import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from rapidfuzz import fuzz, process


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_VERSION_SUFFIX_RE = re.compile(r"(?:[_\-\s]+)?v(?:ersion)?\s*\d+$")


def normalize_title(raw: str) -> str:
    base = raw.lower().strip()
    base, _ = os.path.splitext(base)

    # Extract song title from "Artist_SongTitle" format
    # If there's an underscore, take the part after the last underscore
    if '_' in base:
        parts = base.split('_')
        # Take everything after the first underscore (in case song title has underscores)
        if len(parts) > 1:
            base = '_'.join(parts[1:])

    base = _VERSION_SUFFIX_RE.sub("", base)
    base = _NON_ALNUM_RE.sub(" ", base)
    return re.sub(r"\s+", " ", base).strip()


@dataclass
class MatchResult:
    row_number: int
    row_title: str
    score: float


class SongMatcher:
    def __init__(self, rows: Iterable["SongRow"], threshold: float):
        from .sheets_client import SongRow  # Local import to avoid circular dependency

        self.threshold = threshold * 100  # rapidfuzz returns 0-100
        self._choices: Dict[int, str] = {}
        self._row_lookup: Dict[int, SongRow] = {}
        for row in rows:
            if not row.title:
                continue
            normalized = normalize_title(row.title)
            if not normalized:
                continue
            self._choices[row.row_number] = normalized
            self._row_lookup[row.row_number] = row

    def match(self, candidate_title: str) -> Optional[MatchResult]:
        query = normalize_title(candidate_title)
        if not query or not self._choices:
            return None

        result = process.extractOne(query, self._choices, scorer=fuzz.token_sort_ratio)
        if not result:
            return None

        # process.extractOne returns (matched_value, score, key) when using a dict
        _, score, row_number = result
        if score < self.threshold:
            return None

        matched_row = self._row_lookup[row_number]
        return MatchResult(row_number=row_number, row_title=matched_row.title, score=score / 100.0)
