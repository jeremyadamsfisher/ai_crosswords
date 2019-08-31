PIPENV=pipenv run 
PY=pipenv run python
NCROSSWORDS=1

default: webserver

webserver:
	$(PY) run.py

# crossword generation
gen_crossword:
	$(PY) -W ignore crosswordgen/crosswordgen.py -n $(NCROSSWORDS)
test:
	cd crosswordgen \
	&& $(PY) -W ignore -m pytest -v

# ml
train:
	cd crosswordgen \
	&& $(PIPENV) snakemake -s scrape_and_train_hintgen_model.snakefile
clean:
	cd crosswordgen \
	&& $(PIPENV) black crosswordgen.py \
	&& $(PIPENV) pylint crosswordgen.py
pipenv:
	pipenv update --dev