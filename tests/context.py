"""Put scripts/ on the path so the tests can import the checker directly."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
SCRIPT = os.path.join(ROOT, "scripts", "touchneedle.py")

if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))

import touchneedle as cc  # noqa: E402

__all__ = ["cc", "ROOT", "FIXTURES", "SCRIPT"]
