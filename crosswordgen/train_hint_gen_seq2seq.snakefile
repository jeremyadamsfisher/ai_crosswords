from datetime import timedelta, date
import re
import requests
import csv
import json
import time
import gpt_2_simple as gpt2
import pickle
from pathlib import Path
from tqdm import tqdm
from html import unescape
from collections import defaultdict

rule default:
    input: "checkpoint/run1/checkpoint"

rule download_nyxword_html:
    params:
        base_url = "https://nyxcrossword.com/",
        start_date = (2016, 1, 1),
        end_date = (2017, 1, 1),
    output:
        result_fp = "intermediary/web_dump_results.json",
    run:
        def daterange(start_date, end_date):
            return [
                start_date + timedelta(n)
                for n in range(int((end_date - start_date).days))
            ]
        start_date = date(*params["start_date"])
        end_date = date(*params["end_date"])
        res = {}
        for xword_date in tqdm(daterange(start_date, end_date)):
            url = params["base_url"] + xword_date.strftime("%Y/%m/%d")
            req = requests.get(url)
            res[str(xword_date)] = req.text
        with open(output["result_fp"], "w") as f_out:
            json.dump(res, f_out, indent=4)

rule scrape_nyxword_html:
    input:
        web_dump_results_fp = "intermediary/web_dump_results.json"
    output:
        training_dataset_fp = "intermediary/word2hint.tsv"
    run:
        results = defaultdict(set)
        tag_re = re.compile(r'(<!--.*?-->|<[^>]*>)')
        hint_re = re.compile(r'^\d+. ([^:]+?) : ([A-Z \']+)$', flags=re.MULTILINE)
        with open(input["web_dump_results_fp"]) as f:
            for _, raw_html in json.load(f).items():
                just_text = tag_re.sub('', raw_html)
                for result in re.finditer(hint_re, just_text):
                        hint = unescape(result.group(1).strip())
                        phrase = result.group(2).strip().replace(' ', '')
                        if len(phrase) >= 2 and len(hint) >= 2:
                            results[phrase].add(hint)

        with open(output["training_dataset_fp"], "w") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=["word", "hint"], delimiter="\t")
            for word, hint_set in results.items():
                for hint in hint_set:
                    writer.writerow({"word": word, "hint": hint})

rule train:
    input: 
        train_dataset_fp = "intermediary/word2hint.tsv",
    output:
        model = "checkpoint/run1/checkpoint"
    params:
        epochs = 40
    run:
        model_name = "117M"
        if not (Path("./models") / model_name).exists():
            gpt2.download_gpt2(model_name=model_name)
        sess = gpt2.start_tf_sess()
        gpt2.finetune(
            sess,
            input["train_dataset_fp"],
            model_name=model_name,
            steps=params["epochs"]
        )
        gpt2.generate(sess)