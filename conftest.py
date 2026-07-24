"""Make `sanad_core` importable during tests regardless of invocation cwd.

Tests use small, self-contained, invented sample libraries (see each test
module) -- the suite carries no real-world personal bibliography data.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))
