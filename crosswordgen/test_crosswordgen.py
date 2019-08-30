import pytest
from crosswordgen import Crossword, Orientation, InvalidWordPlacement


@pytest.fixture
def xword():
    with open("wordlist.txt") as f:
        words = set(f)
    return Crossword(grid_len=15, english_word_set=words)


def test_parallel_word_placement(xword):
    xword.place_word((8, 1), Orientation.vertical, "work")
    with pytest.raises(InvalidWordPlacement):
        xword.place_word((1, 1), Orientation.horizontal, "license")


def test_perpendicular_word_placement(xword):
    xword.place_word((1, 1), Orientation.horizontal, "license")
    with pytest.raises(InvalidWordPlacement):
        xword.place_word((8, 1), Orientation.vertical, "work")


def test_word_scan_trivial_example(xword):
    for i, c in enumerate("livid"):
        xword[i, 0] = c
        xword[0, i] = c
    xword[1, 1] = "t"
    print(xword)
    assert xword.words == {
        ('livid', (0, 0), Orientation.vertical),
        ('livid', (0, 0), Orientation.horizontal),
        ('it', (1, 0), Orientation.vertical),
        ('it', (0, 1), Orientation.horizontal),
    }