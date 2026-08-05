from adkar_bot.arabic import shape, wrap_logical

BASMALA = "بسم الله الرحمن الرحيم"
WITH_HARAKAT = "سُبْحَانَ اللَّهِ"


def test_shape_connects_letterforms():
    # Isolated forms must be replaced by contextual presentation forms.
    out = shape(BASMALA)
    assert out != BASMALA
    # U+FEFB is the LAM-ALEF ligature; it appears in shaped output only.
    assert any(0xFE70 <= ord(c) <= 0xFEFF for c in out)


def test_shape_preserves_harakat():
    # arabic_reshaper deletes tashkeel by default. It must not here.
    assert "ْ" in shape(WITH_HARAKAT)  # sukun
    assert "َ" in shape(WITH_HARAKAT)  # fatha


def test_shape_is_pure():
    assert shape(BASMALA) == shape(BASMALA)


def test_wrap_never_splits_a_word():
    fits = lambda s: len(s) <= 10
    lines = wrap_logical("aaa bbb ccc ddd", fits)
    for line in lines:
        for word in line.split():
            assert word in {"aaa", "bbb", "ccc", "ddd"}
    assert " ".join(lines).split() == "aaa bbb ccc ddd".split()


def test_wrap_keeps_oversized_word_on_its_own_line():
    fits = lambda s: len(s) <= 3
    assert wrap_logical("aa bbbbbbbb cc", fits) == ["aa", "bbbbbbbb", "cc"]


def test_wrap_of_empty_text_is_empty():
    assert wrap_logical("   ", lambda s: True) == []


def test_reshape_then_wrap_differs_from_wrap_then_reshape():
    """Regression guard: the ordering rule must not be 'simplified' away.

    Reshaping before wrapping splits presentation forms mid-word.
    """
    fits = lambda s: len(s) <= 12
    correct = [shape(l) for l in wrap_logical(BASMALA, fits)]
    wrong = wrap_logical(shape(BASMALA), fits)
    assert correct != wrong
