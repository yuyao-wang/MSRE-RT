from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_MODEL_DIR = REPO_ROOT / "reference_model"
VERIFICATION_DIR = REPO_ROOT / "verification"


def configure_paths() -> None:
    for path in (REFERENCE_MODEL_DIR, VERIFICATION_DIR, REPO_ROOT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


configure_paths()
