PIPENV=pipenv run 
NCROSSWORDS=1

run:
	$(PIPENV) python -W ignore crosswordgen.py -n $(NCROSSWORDS)

train:
	$(PIPENV) snakemake -s train_hint_gen_seq2seq.snakefile

test:
	$(PIPENV) python -W ignore -m pytest -v

clean:
	$(PIPENV) black crosswordgen.py \
	&& $(PIPENV) pylint crosswordgen.py