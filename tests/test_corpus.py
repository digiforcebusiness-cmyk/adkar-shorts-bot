import json
import pytest
from adkar_bot.corpus import CorpusError, Dhikr, load_corpus
from adkar_bot import config


def write(tmp_path, entries):
    p = tmp_path / "adkar.json"
    p.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return p


VALID = {
    "id": "hisn-0001",
    "text": "سُبْحَانَ اللَّهِ",
    "category": "tasbih",
    "source": "متفق عليه",
    "reference": "البخاري ٦٤٠٦",
}


def test_loads_valid_entries(tmp_path):
    corpus = load_corpus(write(tmp_path, [VALID]))
    assert corpus == [Dhikr(**VALID)]


def test_rejects_duplicate_ids(tmp_path):
    with pytest.raises(CorpusError, match="duplicate"):
        load_corpus(write(tmp_path, [VALID, VALID]))


def test_rejects_missing_text(tmp_path):
    bad = {**VALID, "text": "  "}
    with pytest.raises(CorpusError, match="text"):
        load_corpus(write(tmp_path, [bad]))


def test_rejects_missing_id(tmp_path):
    bad = {k: v for k, v in VALID.items() if k != "id"}
    with pytest.raises(CorpusError, match="id"):
        load_corpus(write(tmp_path, [bad]))


def test_rejects_empty_corpus(tmp_path):
    with pytest.raises(CorpusError, match="empty"):
        load_corpus(write(tmp_path, []))


def test_real_corpus_loads_and_is_nontrivial():
    corpus = load_corpus(config.CORPUS_PATH)
    assert len(corpus) >= 12
    assert len({d.id for d in corpus}) == len(corpus)
