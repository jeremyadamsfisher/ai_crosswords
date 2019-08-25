import json
import random
from pathlib import Path
from flask import render_template
from app import app

crosswords = list(Path(".").glob("crossword-*.json"))

with crosswords[0].open() as f:
    sample_crossword = json.load(f)

@app.route('/')
def show_crossword():
    grid, word2hint = sample_crossword["grid"], sample_crossword["words"]
    return render_template(
        "index.html",
        grid=grid,
        word2hint=word2hint
    )
