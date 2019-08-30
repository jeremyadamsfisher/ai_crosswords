import json
import random
from pathlib import Path
from flask import render_template
from app import app

crosswords = []
for crossword_fp in Path(".").glob("crossword-*.json"):
    with crossword_fp.open() as f:
        crosswords.append(json.load(f))

@app.route('/')
def show_crossword():
    crossword = random.choice(crosswords)
    grid = crossword["grid"]
    word_informations = crossword["words"]
    words = set()
    word_origins = set()
    word_to_origin = {}
    word_to_hint = {}
    word_to_orientation = {}
    for _ in word_informations:
        word = _["word"]
        words.add(word)
        word_origin_x, word_origin_y = _["word_origin"]
        word_origins.add((word_origin_x, word_origin_y))
        word_to_origin[word] = (word_origin_x, word_origin_y)
        orientation = {
            "h": "Across",
            "v": "Down",
        }[_["orientation"]]
        word_to_orientation[word] = orientation
        word_to_hint[word] = _["hint"]
    word_origins = sorted(word_origins, key=lambda origin: (origin[1], origin[0]))
    hint_info = sorted([
        (word_to_hint[word], # hint
         word_origins.index(word_to_origin[word]) + 1,  # associated counter number
         word_to_orientation[word], # orientation
         word)
        for word in words
    ], key=lambda _: _[1])
    hint_info_across = [hint for hint in hint_info if hint[2] is "Across"]
    hint_info_down = [hint for hint in hint_info if hint[2] is "Down"]
    flattened_grid=sum(grid, [])
    grid_len = len(grid)
    flatted_grid_word_origins = [
        origin_y * grid_len + origin_x for (origin_x, origin_y) in word_origins
    ]
    return render_template(
        "crossword.html",
        flattened_grid=flattened_grid,
        flatted_grid_word_origins=flatted_grid_word_origins,
        hint_info_across=hint_info_across,
        hint_info_down=hint_info_down,
    )
