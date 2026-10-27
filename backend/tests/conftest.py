"""
conftest.py – pytest configuration.

Ensures that backend/ is on sys.path for all test modules.
"""

import sys
from pathlib import Path

# Add backend/ to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
