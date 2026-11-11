"""
Phase 3, Step 4: the learning loop.

Combines your hand-labeled prompts with the routing failures the verifier
has collected, retrains the classifier, and saves the new model only if it
still meets the 80% accuracy bar. The previous model is kept as a backup.

The brief suggests running this weekly; for now, run it by hand:
    python retrain.py
To try it on the escalation demo's failure without changing your real model:
    python retrain.py --failures demo_failures.csv --dry-run
"""

import csv
import os
import shutil
import sys

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import FEATURE_NAMES, extract_features
from train_classifier import DATA_FILE, MODEL_FILE, print_confusion_matrix

FAILURES_FILE = "routing_failures.csv"
BACKUP_FILE = "complexity_classifier.previous.joblib"
MIN_ACCURACY = 0.80   # The brief's bar for V1
FAILURE_WEIGHT = 5    # Each real failure counts as 5 examples, so a few can shift the model


def to_features(prompts: list[str]) -> np.ndarray:
    return np.array(
        [[extract_features(p)[name] for name in FEATURE_NAMES] for p in prompts], dtype=float
    )


def load_csv(path: str, tier_column: str) -> dict[str, int]:
    """Read a CSV into {prompt: tier}. Returns an empty dict if the file doesn't exist."""
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["prompt"]: int(row[tier_column]) for row in csv.DictReader(f)}


def main() -> None:
    failures_file = sys.argv[sys.argv.index("--failures") + 1] if "--failures" in sys.argv else FAILURES_FILE
    dry_run = "--dry-run" in sys.argv

    failures = load_csv(failures_file, "corrected_tier")
    if not failures:
        print(f"No routing failures in {failures_file} yet, so there's nothing new to learn.")
        return

    # A failure is newer, real-world evidence, so it replaces any hand label for the same prompt
    labeled = {p: t for p, t in load_csv(DATA_FILE, "tier").items() if p not in failures}
    print(f"Learning from {len(labeled)} hand-labeled prompts + {len(failures)} routing failure(s)\n")

    # Test only on hand-labeled prompts the model never trains on, so scores stay comparable
    prompts = list(labeled)
    train_prompts, test_prompts = train_test_split(
        prompts, test_size=0.2, stratify=[labeled[p] for p in prompts], random_state=42
    )
    train_prompts += list(failures) * FAILURE_WEIGHT
    all_tiers = {**labeled, **failures}
    X_train, y_train = to_features(train_prompts), np.array([all_tiers[p] for p in train_prompts])
    X_test, y_test = to_features(test_prompts), np.array([labeled[p] for p in test_prompts])

    candidates = {
        "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "Random forest": RandomForestClassifier(n_estimators=200, random_state=42),
    }
    best_name, best_model, best_accuracy = "", None, -1.0
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        accuracy = accuracy_score(y_test, model.predict(X_test))
        print(f"{name}: {accuracy:.0%} held-out accuracy")
        if accuracy > best_accuracy:
            best_name, best_model, best_accuracy = name, model, accuracy
    assert best_model is not None

    print(f"\nBest: {best_name}")
    print_confusion_matrix(y_test, best_model.predict(X_test))

    # Did the new model learn the cases the old one got wrong?
    old_model = joblib.load(MODEL_FILE)["model"]
    failure_X = to_features(list(failures))
    failure_y = np.array(list(failures.values()))
    old_right = int((old_model.predict(failure_X) == failure_y).sum())
    new_right = int((best_model.predict(failure_X) == failure_y).sum())
    print(f"\nRouting failures now classified correctly: old model {old_right}/{len(failures)}, "
          f"new model {new_right}/{len(failures)}")

    if best_accuracy < MIN_ACCURACY:
        print(f"\nNot saved: {best_accuracy:.0%} is below the {MIN_ACCURACY:.0%} bar. "
              f"Keeping the current model.")
    elif dry_run:
        print("\nDry run: the new model was not saved.")
    else:
        shutil.copy(MODEL_FILE, BACKUP_FILE)
        joblib.dump({"model": best_model, "feature_names": FEATURE_NAMES}, MODEL_FILE)
        print(f"\nSaved the new model to {MODEL_FILE} (previous one backed up to {BACKUP_FILE}).")
        print("Restart anything that uses the router so it loads the new model.")


if __name__ == "__main__":
    main()