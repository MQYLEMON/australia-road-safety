"""Make the repo root importable so tests can use `from src... import ...`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
