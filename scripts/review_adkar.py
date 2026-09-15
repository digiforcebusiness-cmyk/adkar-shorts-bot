"""Render every extracted adkar entry for reading, before any of it publishes.

Run:  py -3 scripts/review_adkar.py

Writes docs/adkar-review.md. Nothing in the publish path reads it - it exists
because this corpus is machine-extracted from a text that has never been
checked against a printed, scholarly-reviewed edition, and a mis-paired
quotation mark in the source becomes a truncated supplication published six
times a day. The extractor's rules catch malformed quotes, but they are
heuristics, not a scholar. Reading the output once is the only real defence.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADKAR = ROOT / "data" / "adkar.json"
OUT = ROOT / "docs" / "adkar-review.md"


def main(argv=None) -> int:
    entries = json.loads(ADKAR.read_text(encoding="utf-8"))
    extracted = [e for e in entries if e["id"].startswith("adkar-")]
    curated = [e for e in entries if not e["id"].startswith("adkar-")]

    lines = [
        "# Adkar corpus — review copy",
        "",
        f"{len(entries)} entries: {len(curated)} hand-curated "
        f"(Hisn al-Muslim), {len(extracted)} machine-extracted.",
        "",
        "Only the machine-extracted entries are listed below. Read each one and",
        "check it stands alone as a supplication: no dangling conjunction, no",
        "half sentence, no narrator's name. Anything wrong should be deleted",
        "from `data/adkar.json` by its id.",
        "",
    ]
    by_source: dict[str, list[dict]] = {}
    for e in extracted:
        by_source.setdefault(e["source"], []).append(e)

    for source in sorted(by_source, key=lambda s: -len(by_source[s])):
        group = by_source[source]
        lines += [f"## {source} ({len(group)})", ""]
        for e in group:
            lines += [f"- **`{e['id']}`** · {e['reference']} · {e['category']}",
                      f"  > {e['text']}", ""]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(extracted)} entries to review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
