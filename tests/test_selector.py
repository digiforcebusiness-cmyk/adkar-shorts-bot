import json
import pytest
from adkar_bot.corpus import Dhikr
from adkar_bot.selector import State, load_state, next_dhikr, record, save_state


def make_corpus(n):
    return [
        Dhikr(id=f"d{i}", text=f"t{i}", category="c", source="s", reference="r")
        for i in range(n)
    ]


def test_fresh_state_when_file_absent(tmp_path):
    assert load_state(tmp_path / "nope.json") == State(cycle=0, used=[], published=[])


def test_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    s = State(cycle=2, used=["a"], published=[{"id": "a"}])
    save_state(s, p)
    assert load_state(p) == s


def test_no_repeat_within_a_cycle():
    corpus = make_corpus(5)
    state = State(cycle=0, used=[], published=[])
    picked = []
    for _ in range(5):
        d = next_dhikr(corpus, state)
        picked.append(d.id)
        state = record(state, d, "vid", "2026-01-01T00:00:00Z", corpus=corpus)
    assert sorted(picked) == sorted(d.id for d in corpus)


def test_cycle_rolls_over_when_exhausted():
    corpus = make_corpus(3)
    state = State(cycle=0, used=[d.id for d in corpus], published=[])
    d = next_dhikr(corpus, state)
    after = record(state, d, "vid", "2026-01-01T00:00:00Z", corpus=corpus)
    assert after.cycle == 1
    assert after.used == [d.id]


def test_different_cycles_use_different_orders():
    corpus = make_corpus(12)
    def order(cycle):
        state, out = State(cycle=cycle, used=[], published=[]), []
        for _ in range(12):
            d = next_dhikr(corpus, state)
            out.append(d.id)
            state = record(state, d, "v", "t", corpus=corpus)
        return out
    assert order(0) != order(1)


def test_next_dhikr_does_not_mutate_state():
    corpus = make_corpus(3)
    state = State(cycle=0, used=[], published=[])
    next_dhikr(corpus, state)
    assert state == State(cycle=0, used=[], published=[])


def test_order_is_deterministic_for_a_given_cycle():
    corpus = make_corpus(8)
    s = State(cycle=4, used=[], published=[])
    assert next_dhikr(corpus, s).id == next_dhikr(corpus, s).id
