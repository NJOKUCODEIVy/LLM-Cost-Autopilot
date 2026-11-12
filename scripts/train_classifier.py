"""
Phase 2, Step 3: train the complexity classifier.

    python -m scripts.train_classifier

Turns every labeled prompt into features, trains two simple scikit-learn
models (logistic regression and random forest), reports their accuracy and
confusion matrix on a held-out test set, and saves the better one.
"""

import csv

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import FEATURE_NAMES, extract_features
from paths import CLASSIFIER, LABELED_PROMPTS

DATA_FILE = LABELED_PROMPTS
MODEL_FILE = CLASSIFIER


def load_dataset() -> tuple[np.ndarray, np.ndarray]:
    """Return the features (X) and tier labels (y) as NumPy arrays."""
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    X = np.array(
        [[extract_features(r["prompt"])[name] for name in FEATURE_NAMES] for r in rows],
        dtype=float,
    )
    y = np.array([int(r["tier"]) for r in rows])
    return X, y


def print_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> None:
    matrix = confusion_matrix(y_true, y_pred, labels=[1, 2, 3])
    print("                Predicted")
    print("              T1   T2   T3")
    for tier, row in zip([1, 2, 3], matrix):
        print(f"    Actual T{tier} " + "".join(f"{n:>4} " for n in row))


def main() -> None:
    X, y = load_dataset()

    # Hold back 20% of prompts that the models never see during training
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print(f"Training on {len(X_train)} prompts, testing on {len(X_test)} held-out prompts\n")

    models = {
        "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "Random forest": RandomForestClassifier(n_estimators=200, random_state=42),
    }

    best_name, best_model, best_accuracy = None, None, -1.0
    for name, model in models.items():
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        accuracy = accuracy_score(y_test, predictions)
        # 5-fold cross-validation: train and test 5 times on different splits for a steadier score
        cv_scores = cross_val_score(model, X, y, cv=5)

        print(f"=== {name} ===")
        print(f"Held-out accuracy:        {accuracy:.0%}")
        print(f"5-fold cross-validation:  {cv_scores.mean():.0%} (+/- {cv_scores.std():.0%})")
        print_confusion_matrix(y_test, predictions)
        print()

        if accuracy > best_accuracy:
            best_name, best_model, best_accuracy = name, model, accuracy

    joblib.dump({"model": best_model, "feature_names": FEATURE_NAMES}, MODEL_FILE)
    verdict = "meets" if best_accuracy >= 0.8 else "is below"
    print(f"Saved {best_name} to {MODEL_FILE}")
    print(f"Its held-out accuracy of {best_accuracy:.0%} {verdict} the brief's 80% target for V1.")


if __name__ == "__main__":
    main()
