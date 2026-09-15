"""One-off: split the mixed corpus and rotation state into two profiles.

Run once:  py -3 scripts/split_corpus.py

data/adkar.json holds 7,888 entries from three sources. After this it holds
only the 206 Hisn al-Muslim adkar; the 7,682 Bukhari and Muslim entries move
to data/hadith.json.

The state split is deliberately not a clean partition. data/state.json's 33
used ids are all hisn-*, but those videos are on the hadith channel. So:
hadith keeps the publish records (the only audit trail of what is on that
channel) but starts with used: [], because no hadith has ever published;
adkar starts empty, because @DIKR-o6k has published nothing and all 206
entries should be available to it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _write(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv=None) -> int:
    source = DATA / "adkar.json"
    corpus = json.loads(source.read_text(encoding="utf-8"))

    hisn = [e for e in corpus if e["id"].startswith("hisn-")]
    hadith = [e for e in corpus if e["id"].startswith(("bukhari-", "muslim-"))]

    # Refuse rather than partition partially. Writing adkar.json is
    # destructive - anything matching neither prefix would be deleted with no
    # copy anywhere, and nothing downstream would ever notice.
    if len(hisn) + len(hadith) != len(corpus):
        known = {e["id"] for e in hisn} | {e["id"] for e in hadith}
        stray = sorted({e["id"] for e in corpus} - known)
        print(f"refusing to split: {len(stray)} entries match no known id "
              f"prefix, e.g. {stray[:5]}", file=sys.stderr)
        return 1

    _write(DATA / "hadith.json", hadith)
    _write(source, hisn)

    old_state = DATA / "state.json"
    history = []
    if old_state.exists():
        history = json.loads(old_state.read_text(encoding="utf-8")).get("published", [])
    _write(DATA / "state-hadith.json",
           {"cycle": 0, "used": [], "published": history})
    _write(DATA / "state-adkar.json",
           {"cycle": 0, "used": [], "published": []})
    old_state.unlink(missing_ok=True)

    print(f"hadith {len(hadith)} | adkar {len(hisn)} | "
          f"history preserved on hadith {len(history)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
