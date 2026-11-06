"""Meridian — agentic portfolio management platform."""
from pathlib import Path

__version__ = "0.1.0"
import os

# repo root holds config/, policies/, regimes/, agents/, skills/ (overridable for installed/container use)
REPO_ROOT = Path(os.getenv("MERIDIAN_REPO_ROOT") or Path(__file__).resolve().parents[2])
