import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set


@dataclass
class FileRowBinding:
    row_number: int
    title: str

    def to_json(self) -> Dict[str, object]:
        return {"row_number": self.row_number, "title": self.title}

    @classmethod
    def from_json(cls, payload: Dict[str, object]) -> "FileRowBinding":
        return cls(
            row_number=int(payload.get("row_number", 0)),
            title=str(payload.get("title", "")),
        )


@dataclass
class ProcessedState:
    processed_comment_ids: Set[str] = field(default_factory=set)
    file_row_cache: Dict[str, FileRowBinding] = field(default_factory=dict)
    last_polled: Optional[str] = None

    def to_json(self) -> Dict[str, object]:
        return {
            "processed_comment_ids": sorted(self.processed_comment_ids),
            "file_row_cache": {file_id: binding.to_json() for file_id, binding in self.file_row_cache.items()},
            "last_polled": self.last_polled,
        }

    @classmethod
    def from_json(cls, payload: Dict[str, object]) -> "ProcessedState":
        processed_comment_ids = set(payload.get("processed_comment_ids", []))
        raw_cache = payload.get("file_row_cache", {})
        file_row_cache = {}
        if isinstance(raw_cache, dict):
            for file_id, binding in raw_cache.items():
                if isinstance(binding, dict):
                    file_row_cache[file_id] = FileRowBinding.from_json(binding)
        last_polled = payload.get("last_polled")
        return cls(
            processed_comment_ids=processed_comment_ids,
            file_row_cache=file_row_cache,
            last_polled=last_polled,
        )


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> ProcessedState:
        if not self.path.exists():
            return ProcessedState()
        with self.path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return ProcessedState.from_json(payload)

    def save(self, state: ProcessedState) -> None:
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as fh:
            json.dump(state.to_json(), fh, indent=2, sort_keys=True)
            fh.write("\n")
        temp_path.replace(self.path)
