"""
Phase 2, Step 4: the router.

Predicts a prompt's complexity tier with the trained classifier, looks up
which model handles that tier in routing.yaml, sends the prompt, and logs
the request to autopilot.db.
"""

import sys

import joblib
import numpy as np
import yaml

from features import extract_features
from logger import log_request
from providers import Response, send_request
from registry import MODEL_REGISTRY, ModelConfig

ROUTING_FILE = "routing.yaml"
MODEL_FILE = "complexity_classifier.joblib"


def load_routing_map() -> dict:
    """Read routing.yaml and check that every model it names exists in the registry."""
    with open(ROUTING_FILE, encoding="utf-8") as f:
        routing = yaml.safe_load(f)
    named = list(routing["tiers"].values())
    for section in ("fallback", "escalation"):
        named += list(routing[section].keys()) + list(routing[section].values())
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


def route(prompt: str) -> tuple[int, int, Response]:
    """Pick a model, send the prompt, log it, and return (request_id, tier, Response).

    If the routed model's provider fails (down, overloaded, or too slow), the
    prompt goes to that model's fallback from routing.yaml instead.
    """
    tier, model = choose_model(prompt)
    fallback_from = None
    try:
        response = send_request(prompt, model)
    except Exception as error:
        backup = MODEL_REGISTRY[ROUTING["fallback"][model.name]]
        print(f"    {model.name} failed ({type(error).__name__}); falling back to {backup.name}")
        fallback_from, model = model.name, backup
        response = send_request(prompt, model)

    request_id = log_request(
        prompt, tier, model.name, response.input_tokens, response.output_tokens,
        response.cost, response.latency, fallback_from,
    )
    return request_id, tier, response


if __name__ == "__main__":
    examples = [
        "Convert 9 kilometers to miles.",
        "Extract the date from: 'The invoice was issued on 2 March 2026.'",
        "Summarize this in one sentence: 'Our team grew from 5 to 12 people this year, and we opened a second office in Abuja to serve clients in the north.'",
        "Classify this review as positive, negative, or mixed: 'Fast shipping, but the box was damaged.'",
        "Compare renting and buying a car for a new graduate in Lagos, and recommend one.",
        "Write a short poem about rain on a tin roof with an AABB rhyme scheme.",
    ]

    if "--send" in sys.argv:
        # Real requests: each one is routed, answered, and logged to autopilot.db
        for prompt in examples:
            request_id, tier, r = route(prompt)
            print(f"#{request_id} Tier {tier} -> {r.model_id:<22} ${r.cost:.7f} | {prompt[:45]}")
    else:
        # Routing decisions only: no API calls, nothing logged
        for prompt in examples:
            tier, model = choose_model(prompt)
            print(f"Tier {tier} -> {model.name:<22} | {prompt[:60]}")