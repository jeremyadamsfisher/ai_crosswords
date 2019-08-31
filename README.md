# ai_crosswords
generate crosswords with the power of AI 🦄✨

This code base includes the front-end (under `app`) and the crossword generation code (under `crosswordgen`).

To serve the website, use the default rule for `make`.

The crossword generation workflow is as follows:
1. *Either* run the `make train` to train the hint generation model *or* download the pre-trained weights (contact me at jeremyadamsfisher@gmail.com)
2. Generate crosswords with `make gen_crossword`

The crossword generation itself has unit tests which can be run with `make test`.

Make sure to install pipenv beforehand.
