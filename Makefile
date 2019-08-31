PIPENV=pipenv run 
PY=pipenv run python
NCROSSWORDS=1

default: webserver

webserver:
	$(PY) run.py
gen_crossword:
	$(PY) -W ignore crosswordgen/crosswordgen.py -n $(NCROSSWORDS)
train:
	$(PIPENV) snakemake -s crosswordgen/train_hint_gen_seq2seq.snakefile
test:
	cd crosswordgen \
	&& $(PY) -W ignore -m pytest -v
clean:
	cd crosswordgen \
	&& $(PIPENV) black crosswordgen.py \
	&& $(PIPENV) pylint crosswordgen.py