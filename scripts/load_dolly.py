"""
Phase 6, Step 1b: pick 1,000 real, human-written prompts for the load test.

Downloads the Databricks Dolly 15k dataset (written by Databricks employees,
licensed CC BY-SA 3.0) and samples 125 prompts from each of its 8 categories,
so every kind of request is equally represented. The sample is the same every
time you run it (fixed random seed), so the load test is reproducible.

    python -m scripts.load_dolly
"""

import csv
import json
import os
import random
import re

import requests

from paths import DOLLY_RAW, LOAD_TEST_PROMPTS

DOLLY_URL = ("https://huggingface.co/datasets/databricks/databricks-dolly-15k"
             "/resolve/main/databricks-dolly-15k.jsonl")
RAW_FILE = DOLLY_RAW
OUTPUT_FILE = LOAD_TEST_PROMPTS
PER_CATEGORY = 125      # 8 categories x 125 = 1,000 prompts
MAX_CHARS = 2_000       # Skip very long prompts to keep token use reasonable
SEED = 42


def download() -> None:
    """Download the dataset once (about 13 MB); later runs reuse the saved copy."""
    if os.path.exists(RAW_FILE):
        return
    os.makedirs(RAW_FILE.parent, exist_ok=True)
    print("Downloading Dolly 15k (about 13 MB)...")
    response = requests.get(DOLLY_URL, timeout=120)
    response.raise_for_status()
    with open(RAW_FILE, "wb") as f:
        f.write(response.content)


def to_prompt(record: dict) -> str:
    """Combine the instruction with its reference text, if it has one."""
    instruction = record["instruction"].strip()
    context = re.sub(r"\s*\[\d+\]", "", record.get("context", "")).strip()  # Drop Wikipedia [12] markers
    # "Text:" is a label the feature extractor recognizes as provided context
    return f"{instruction}\n\nText: {context}" if context else instruction


def main() -> None:
    download()
    by_category: dict[str, list[str]] = {}
    with open(RAW_FILE, encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            prompt = to_prompt(record)
            if 0 < len(prompt) <= MAX_CHARS:
                by_category.setdefault(record["category"], []).append(prompt)

    rng = random.Random(SEED)
    rows = []
    for category in sorted(by_category):
        prompts = sorted(set(by_category[category]))  # Remove duplicates; sort so the seed gives the same sample
        for prompt in rng.sample(prompts, min(PER_CATEGORY, len(prompts))):
            rows.append({"category": category, "prompt": prompt})
    rng.shuffle(rows)  # Mix categories, like real traffic

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "category", "prompt"])
        writer.writeheader()
        for i, row in enumerate(rows, start=1):
            writer.writerow({"id": i, **row})

    print(f"Saved {len(rows)} prompts to {OUTPUT_FILE}:")
    for category in sorted(by_category):
        count = sum(1 for r in rows if r["category"] == category)
        print(f"  {category:<24} {count}")


if __name__ == "__main__":
    main()
