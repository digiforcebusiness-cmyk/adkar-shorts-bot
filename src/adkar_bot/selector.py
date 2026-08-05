import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .corpus import Dhikr


@dataclass(frozen=True)
class State:
    cycle: int = 0
    used: list[str] = field(default_factory=list)
    published: list[dict] = field(default_factory=list)


def load_state(path: Path) -> State:
    path = Path(path)
    if not path.exists():
        return State()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return State(
        cycle=raw.get("cycle", 0),
        used=raw.get("used", []),
        published=raw.get("published", []),
    )


def save_state(state: State, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _shuffled(corpus: list[Dhikr], cycle: int) -> list[Dhikr]:
    ordered = sorted(corpus, key=lambda d: d.id)
    random.Random(cycle).shuffle(ordered)
    return ordered


def _effective(state: State, corpus: list[Dhikr]) -> tuple[int, set[str]]:
    """Roll the cycle over if every id has been used."""
    ids = {d.id for d in corpus}
    if ids and ids.issubset(set(state.used)):
        return state.cycle + 1, set()
    return state.cycle, set(state.used)


def next_dhikr(corpus: list[Dhikr], state: State) -> Dhikr:
    cycle, used = _effective(state, corpus)
    for dhikr in _shuffled(corpus, cycle):
        if dhikr.id not in used:
            return dhikr
    raise RuntimeError("unreachable: cycle rollover guarantees an unused entry")


def record(state: State, dhikr: Dhikr, video_id: str, at: str,
           corpus: list[Dhikr]) -> State:
    """Return a new state with `dhikr` marked used and the publish logged.

    `corpus` is required so this reproduces exactly the rollover decision
    `next_dhikr` made from the same inputs. One code path, no inference.
    """
    cycle, used = _effective(state, corpus)
    return State(
        cycle=cycle,
        used=sorted(used | {dhikr.id}),
        published=[*state.published,
                   {"id": dhikr.id, "video_id": video_id, "at": at}],
    )
