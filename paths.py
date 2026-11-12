"""
Where every file in the project lives, in one place.

Paths are built from this file's location, so scripts work no matter which
folder you run them from.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"      # Prompts, results, and training data
DB_DIR = ROOT / "db"          # SQLite request logs (kept out of Git)
MODELS_DIR = ROOT / "models"  # The trained complexity classifier

# Data
LABELED_PROMPTS = DATA_DIR / "labeled_prompts.csv"
LOAD_TEST_PROMPTS = DATA_DIR / "load_test_prompts.csv"
LOAD_TEST_PROGRESS = DATA_DIR / "load_test_progress.txt"
BASELINE_RESULTS = DATA_DIR / "baseline_results.csv"
ROUTING_FAILURES = DATA_DIR / "routing_failures.csv"
DOLLY_RAW = DATA_DIR / "raw" / "databricks-dolly-15k.jsonl"

# Model and config
CLASSIFIER = MODELS_DIR / "complexity_classifier.joblib"
CLASSIFIER_BACKUP = MODELS_DIR / "complexity_classifier.previous.joblib"
ROUTING_CONFIG = ROOT / "routing.yaml"

# Databases (each can be overridden with the AUTOPILOT_DB environment variable)
DB_DIR.mkdir(exist_ok=True)
DEFAULT_DB = DB_DIR / "autopilot.db"
