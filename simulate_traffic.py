"""
Phase 4: send realistic traffic through the full Autopilot.

Gives the dashboard real data to show. It uses prompts the classifier never
trained on: the 42 held-out prompts from labeled_prompts.csv plus your 10
baseline questions. Each one goes through autopilot.handle(), which routes it,
logs it, and checks about 1 in 3 answers in the background, just like real use.

    python simulate_traffic.py            # all 52 prompts
    python simulate_traffic.py --limit 10 # a quick, smaller run
"""

import csv
import sys
import time

from sklearn.model_selection import train_test_split

from autopilot import handle
from test_prompts import TEST_PROMPTS
from verifier import wait_until_done

PAUSE_SECONDS = 2  # Space out requests to stay within free-tier rate limits


def unseen_prompts() -> list[str]:
    """The held-out prompts (same split as training, so the classifier never saw them),
    plus the baseline questions."""
    with open("labeled_prompts.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    prompts = [r["prompt"] for r in rows]
    tiers = [int(r["tier"]) for r in rows]
    _, held_out = train_test_split(prompts, test_size=0.2, stratify=tiers, random_state=42)
    return held_out + [item["prompt"] for item in TEST_PROMPTS]


def main() -> None:
    prompts = unseen_prompts()
    if "--limit" in sys.argv:
        prompts = prompts[: int(sys.argv[sys.argv.index("--limit") + 1])]

    print(f"Sending {len(prompts)} prompts through the Autopilot...\n")
    total_cost, failed = 0.0, 0
    for i, prompt in enumerate(prompts, start=1):
        try:
            response = handle(prompt)
            total_cost += response.cost
            print(f"[{i}/{len(prompts)}] {response.model_id:<22} ${response.cost:.7f} | {prompt[:50]}")
        except Exception as error:
            failed += 1
            print(f"[{i}/{len(prompts)}] FAILED ({type(error).__name__}) | {prompt[:50]}")
        time.sleep(PAUSE_SECONDS)

    print("\nWaiting for background quality checks to finish...")
    wait_until_done()
    print(f"\nDone: {len(prompts) - failed} answered, {failed} failed, "
          f"answer cost ${total_cost:.6f}. Open the dashboard to see the results.")


if __name__ == "__main__":
    main()