from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = REPO_ROOT / "python"
VERIFICATION_DIR = REPO_ROOT / "Verification_Evaluation"


def configure_paths() -> None:
    for path in (PYTHON_DIR, VERIFICATION_DIR, REPO_ROOT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


configure_paths()
