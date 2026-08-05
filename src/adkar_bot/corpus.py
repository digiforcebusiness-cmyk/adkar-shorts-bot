import json
from dataclasses import dataclass
from pathlib import Path

from . import config


class CorpusError(RuntimeError):
    pass


@dataclass(frozen=True)
class Dhikr:
    id: str
    text: str
    category: str
    source: str
    reference: str


_REQUIRED = ("id", "text", "category", "source", "reference")


def load_corpus(path: Path | None = None) -> list[Dhikr]:
    path = path or config.CORPUS_PATH
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    if not raw:
        raise CorpusError(f"corpus at {path} is empty")

    seen: set[str] = set()
    out: list[Dhikr] = []
    for i, entry in enumerate(raw):
        for field in _REQUIRED:
            if field not in entry:
                raise CorpusError(f"entry {i} is missing required field {field!r}")
            if not str(entry[field]).strip():
                raise CorpusError(f"entry {i} has blank field {field!r}")
        if entry["id"] in seen:
            raise CorpusError(f"duplicate id {entry['id']!r}")
        seen.add(entry["id"])
        out.append(Dhikr(**{f: entry[f] for f in _REQUIRED}))
    return out
