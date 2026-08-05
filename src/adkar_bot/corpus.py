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
    path = Path(path or config.CORPUS_PATH)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"corpus at {path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, list):
        raise CorpusError(
            f"corpus at {path} must be a JSON array, got {type(raw).__name__}"
        )
    if not raw:
        raise CorpusError(f"corpus at {path} is empty")

    seen: set[str] = set()
    out: list[Dhikr] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise CorpusError(
                f"entry {i} must be a JSON object, got {type(entry).__name__}"
            )
        for field in _REQUIRED:
            if field not in entry:
                raise CorpusError(f"entry {i} is missing required field {field!r}")
            value = entry[field]
            # isinstance guards None, ints and every other non-string: the
            # str()-then-strip() form silently accepts null as the text "None".
            if not isinstance(value, str) or not value.strip():
                raise CorpusError(
                    f"entry {i} has blank or non-string field {field!r}"
                )
        if entry["id"] in seen:
            raise CorpusError(f"duplicate id {entry['id']!r}")
        seen.add(entry["id"])
        out.append(Dhikr(**{f: entry[f] for f in _REQUIRED}))
    return out
