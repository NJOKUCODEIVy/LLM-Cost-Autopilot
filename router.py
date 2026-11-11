"""
Phase 2, Step 4: the router.

Predicts a prompt's complexity tier with the trained classifier, then looks
up which model handles that tier in routing.yaml.
"""

import joblib
import numpy as np
import yaml

from features import extract_features
from providers import Response, send_request
from registry import MODEL_REGISTRY, ModelConfig

ROUTING_FILE = "routing.yaml"
MODEL_FILE = "complexity_classifier.joblib"


def load_routing_map() -> dict:
    """Read routing.yaml and check that every model it names exists in the registry."""
    with open(ROUTING_FILE, encoding="utf-8") as f:
        routing = yaml.safe_load(f)
    named = list(routing["tiers"].values())
    named += list(routing["escalation"].keys()) + list(routing["escalation"].values())
    for name in named:
        if name not in MODEL_REGISTRY:
            raise ValueError(f"routing.yaml names '{name}', which is not in MODEL_REGISTRY")
    return routing


ROUTING = load_routing_map()
_saved = joblib.load(MODEL_FILE)
CLASSIFIER = _saved["model"]
FEATURE_NAMES = _saved["feature_names"]


def predict_tier(prompt: str) -> int:
    """Return the predicted complexity tier (1, 2, or 3) for a prompt."""
    features = extract_features(prompt)
    row = np.array([[features[name] for name in FEATURE_NAMES]], dtype=float)
    return int(CLASSIFIER.predict(row)[0])


def choose_model(prompt: str) -> tuple[int, ModelConfig]:
    """Return the predicted tier and the model that routing.yaml assigns to it."""
    tier = predict_tier(prompt)
    return tier, MODEL_REGISTRY[ROUTING["tiers"][tier]]


def route(prompt: str) -> tuple[int, Response]:
    """Pick the right model for a prompt, send it, and return the tier and Response."""
    tier, model = choose_model(prompt)
    return tier, send_request(prompt, model)


if __name__ == "__main__":
    # New prompts the classifier has never seen. This only shows routing decisions,
    # so it makes no API calls.
    examples = [
        "Convert 9 kilometers to miles.",
        "Extract the date from: 'The invoice was issued on 2 March 2026.'",
        "Summarize this in one sentence: 'Our team grew from 5 to 12 people this year, and we opened a second office in Abuja to serve clients in the north.'",
        "Classify this review as positive, negative, or mixed: 'Fast shipping, but the box was damaged.'",
        "Compare renting and buying a car for a new graduate in Lagos, and recommend one.",
        "Write a short poem about rain on a tin roof with an AABB rhyme scheme.",
    ]
    for prompt in examples:
        tier, model = choose_model(prompt)
        print(f"Tier {tier} -> {model.name:<22} | {prompt[:60]}")
        