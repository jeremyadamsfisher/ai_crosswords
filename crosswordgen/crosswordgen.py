"""generates crosswords, including the hint by using 
GPT-2 fine-tuned on scraped crossword hints

Requires a word list, i.e. a text document with one
word per line. By default, the program looks for this
at ./wordlist.txt

"""


from typing import Tuple, Set, List
import multiprocessing as mp
import collections
import random
import enum
import time
import argparse
import json
import uuid
import pprint
from pathlib import Path
from itertools import count

from tqdm import tqdm
import gpt_2_simple as gpt2

class WorkflowError(Exception):
    """if something in the workflow is run out of sequence"""

sess = gpt2.start_tf_sess()
try:
    gpt2.load_gpt2(sess)
except FileNotFoundError:
    raise WorkflowError(
        "Cannot find GPT-2 checkpoint. Try running "
        "the snakemake workflow before using this tool."
    )

def cli() -> dict:
    """command line interface"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid-len", dest="grid_len", type=int, default=15)
    parser.add_argument(
        "--wordlist-fp",
        dest="wordlist_fp",
        default=Path("./wordlist.txt"),
        type=lambda fp: Path(fp).resolve(),
    )
    parser.add_argument(
        "--n-crosswords", "-n", dest="n_crosswords", default=1, type=int
    )
    return parser.parse_args().__dict__


class Orientation(enum.Enum):
    """a word property"""

    horizontal = "h"
    vertical = "v"


class Flow(enum.Enum):
    """used to keep track of how a word was laid down; allows
    placement of a words perpendicularly"""

    left_right = "lr"
    top_bottom = "tb"
    bidirectional = "ni"


class Direction(enum.Enum):
    """used when scanning for words in radiate() and walk()"""

    up = "up"
    down = "down"
    left = "left"
    right = "right"


class InvalidWordPlacement(Exception):
    """whenever a word placement is unacceptable"""


class Crossword:
    """storage class that also checks for word placement validity. Notably,
    it does not actually build the crossword; that is implemented in create_crossword()"""

    def __init__(self, grid_len, english_word_set):
        self.filled_points = set()
        self.flow = {}
        self.grid_len = grid_len
        self.word2hint = {}
        self.crossword_grid = [[None for _ in range(grid_len)] for _ in range(grid_len)]
        self.english_word_set = english_word_set

    def __getitem__(self, idx: Tuple[int, int]):
        x, y = idx
        if x < 0 or self.grid_len <= x or y < 0 or self.grid_len <= y:
            raise IndexError(f"{(x, y)} out of bounds!")
        return self.crossword_grid[y][x]

    def __setitem__(self, idx: Tuple[int, int], char: str):
        if not len(char) == 1:
            raise TypeError(char)
        x, y = idx
        self[x, y]  # make sure we are within bounds
        self.filled_points.add((x, y))
        self.crossword_grid[y][x] = char

    def grab_random_filled_point(self):
        return random.choice(list(self.filled_points))

    def place_word(self, origin: Tuple[int, int], orientation: Orientation, word: int):
        x_origin, y_origin = origin
        if orientation == Orientation.vertical:
            coordinates = [(x_origin, y_origin + i) for i in range(self.grid_len)]
        else:
            coordinates = [(x_origin + i, y_origin) for i in range(self.grid_len)]
        for (_x, _y), letter in zip(coordinates, word):
            try:
                current_letter_at_cursor = self[_x, _y]
            except IndexError:
                raise InvalidWordPlacement(
                    f"({_x}, {_y}) is not part of the crossword grid!"
                )
            else:
                if current_letter_at_cursor and current_letter_at_cursor != letter:
                    raise InvalidWordPlacement("Letters and blanks do not match!")

                # check for words formed perpendicularly by adding individual numbers
                perpendicular_letters = collections.deque([letter])
                for offsets, append_method in [
                    (
                        ((x_origin - offset, _y) for offset in count(1)),
                        perpendicular_letters.appendleft,
                    ),
                    (
                        ((x_origin + offset, _y) for offset in count(1)),
                        perpendicular_letters.append,
                    ),
                    (
                        ((_x, y_origin - offset) for offset in count(1)),
                        perpendicular_letters.appendleft,
                    ),
                    (
                        ((_x, y_origin + offset) for offset in count(1)),
                        perpendicular_letters.append,
                    ),
                ]:
                    for offset in offsets:
                        try:
                            c = self[offset]
                            assert c is not None
                        except (IndexError, AssertionError):
                            break
                        else:
                            append_method(c)
                if 1 < len(perpendicular_letters):
                    try:
                        perpendicular_word = "".join(perpendicular_letters)
                    except TypeError:
                        raise TypeError(perpendicular_letters)
                    if perpendicular_word not in self.english_word_set:
                        raise InvalidWordPlacement

        # check that the whole word is actually in the dictionary
        parellel_letters = collections.deque(word)
        if orientation == Orientation.horizontal:
            projection = [
                (
                    ((x_origin - offset, y_origin) for offset in count(start=1)),
                    parellel_letters.appendleft,
                ),
                (
                    (
                        (x_origin + offset, y_origin)
                        for offset in count(start=len(word))
                    ),
                    parellel_letters.append,
                ),
            ]
        else:
            projection = [
                (
                    ((x_origin, y_origin - offset) for offset in count(start=1)),
                    parellel_letters.appendleft,
                ),
                (
                    (
                        (x_origin, y_origin + offset)
                        for offset in count(start=len(word))
                    ),
                    parellel_letters.append,
                ),
            ]
        for offsets, append_method in projection:
            for offset in offsets:
                try:
                    c = self[offset]
                    assert c is not None
                except (IndexError, AssertionError):
                    break
                else:
                    append_method(c)
        parellel_word = "".join(parellel_letters)
        if len(word) < len(parellel_word):
            raise InvalidWordPlacement("{parellel_word} overlaps {word}")

        for (_x, _y), letter in zip(coordinates, word):
            if not self[_x, _y]:
                self[_x, _y] = letter
                self.flow[_x, _y] = {
                    Orientation.horizontal: Flow.left_right,
                    Orientation.vertical: Flow.top_bottom,
                }[orientation]
            else:
                self.flow[_x, _y] = Flow.bidirectional

    def __repr__(self):
        return "\n".join(
            " ".join(col if col else "░" for col in row) for row in self.crossword_grid
        )

    def to_dict(self):
        json_serializable_words = []
        for (word, word_origin, orientation), hint in self.word2hint.items():
            json_serializable_words.append(
                {
                    "word": word,
                    "word_origin": word_origin,
                    "orientation": orientation.value,
                    "hint": hint,
                }
            )
        return {"words": json_serializable_words, "grid": self.crossword_grid}

    @property
    def words(self):
        _words = set()

        def radiate(orientation, starting_coord) -> Tuple[Tuple[int, int], str]:
            x_start, y_start = starting_coord

            def walk(current_coord, direction, path) -> List[Tuple[int, int]]:
                try:
                    assert self[current_coord] is not None
                except (
                    IndexError,
                    AssertionError,
                ):  # base case, we've reached an edge or an open space
                    return path
                else:
                    x, y = current_coord
                    if direction == Direction.up:
                        return walk((x, y - 1), Direction.up, [current_coord] + path)
                    elif direction == Direction.down:
                        return walk((x, y + 1), Direction.down, path + [current_coord])
                    elif direction == Direction.left:
                        return walk((x - 1, y), Direction.left, [current_coord] + path)
                    elif direction == Direction.right:
                        return walk((x + 1, y), Direction.right, path + [current_coord])

            if orientation == Orientation.vertical:
                word_coords = (
                    walk((x_start, y_start - 1), Direction.up, [])
                    + [starting_coord]
                    + walk((x_start, y_start + 1), Direction.down, [])
                )
            else:
                word_coords = (
                    walk((x_start - 1, y_start), Direction.left, [])
                    + [starting_coord]
                    + walk((x_start + 1, y_start), Direction.right, [])
                )
            word_origin = word_coords[0]
            word = "".join(self[coord] for coord in word_coords)
            return word_origin, word

        for coord in self.filled_points:
            for orientation in [Orientation.vertical, Orientation.horizontal]:
                word_origin, word = radiate(orientation, coord)
                if 1 < len(word):
                    _words.add((word, word_origin, orientation))
        return _words


def create_crossword(
    english_word_set: Set[str],
    seed=None,
    grid_len=15,
    n_words=35,
    timeout=5
):
    """create a crossword, from scratch
    
    Arguments:
        english_word_set {Set[str]} -- all sequences that will be considered valid
    
    Keyword Arguments:
        seed {[type]} -- random seed for how the word grid is generated (but not the hints)
        grid_len {int} -- length of the grid (default: {15})
        n_words {int} -- minimum words to generate (default: {35})
        timeout {int} -- second before timing out (default: {5})
    
    Returns:
        [Crossword] -- the computer-generated crossword
    """
    english_words = sorted(english_word_set)
    words_containing_letter = collections.defaultdict(list)
    for word in english_word_set:
        for i, letter in enumerate(word):
            words_containing_letter[letter].append((word, i))

    start = time.time()
    if seed:
        random.seed(seed)
    crossword = Crossword(grid_len, english_word_set)
    seed_word = random.choice(english_words)
    orientation = Orientation.horizontal
    crossword.place_word((3, grid_len // 2), orientation, seed_word)
    while True:
        if timeout and (timeout < time.time() - start):
            break
        next_pivot_x, next_pivot_y = crossword.grab_random_filled_point()
        letter_to_fill = crossword[next_pivot_x, next_pivot_y]
        flow = crossword.flow[next_pivot_x, next_pivot_y]
        if flow == Flow.bidirectional:
            continue
        elif flow == Flow.top_bottom:
            orientation = Orientation.horizontal
        elif flow == Flow.left_right:
            orientation = Orientation.vertical
        try:
            next_word, index_of_letter = random.choice(
                words_containing_letter[letter_to_fill]
            )
            if orientation == Orientation.vertical:
                origin_x, origin_y = next_pivot_x, next_pivot_y - index_of_letter
            else:
                origin_x, origin_y = next_pivot_x - index_of_letter, next_pivot_y
            crossword.place_word((origin_x, origin_y), orientation, next_word)
        except (InvalidWordPlacement, IndexError):
            pass
        else:
            if len(crossword.words) == n_words:
                break
    print("Generated the following word grid:")
    print(crossword)
    print("Now generating hints...")
    for word_info in tqdm(crossword.words, unit="word"):
        word, _, _ = word_info
        while True:
            text_gen = gpt2.generate(
                sess,
                run_name="run1",
                prefix=word.upper() + "\t",
                return_as_list=True,
                length=20,
            )[0]
            s = text_gen.split("\n")[0].split("\t")
            if len(s) == 2 and word.lower() == s[0].lower():
                _, hint = s
                print(f"\t{word}: {hint}")
                crossword.word2hint[word_info] = hint
                break
    return crossword


def main(wordlist_fp: Path, grid_len: int, n_crosswords: int):
    """orchestration function; just a wrapper to load stuff to execute create_crossword()
    
    Arguments:
        wordlist_fp {Path} -- path  to the list of words, one word per line
        grid_len {int} -- size of the crossword
        n_crosswords {int} -- number of crosswords to generate per session
    
    Raises:
        FileNotFoundError: When the GPT-2 model weights cannot be found
    """
    if not Path("./checkpoint/run1").exists():
        raise FileNotFoundError("Cannot find fine-tuned GPT-2 model!")
    min_len, max_lex = 2, grid_len - 6
    with open(wordlist_fp) as f:
        english_word_set = {
            line.strip().lower()
            for line in f
            if min_len <= len(line.strip()) <= max_lex
        }
    outpath = Path("./output")
    outpath.mkdir(exists_ok=True)
    for i in range(n_crosswords):
        print(f"Building crossword {i}/{n_crosswords}")
        crossword = create_crossword(english_word_set, grid_len=grid_len)
        with (outpath/f"crossword-{uuid.uuid4()}.json").open("w") as f:
            json.dump(crossword.to_dict(), f)


if __name__ == "__main__":
    main(**cli())
