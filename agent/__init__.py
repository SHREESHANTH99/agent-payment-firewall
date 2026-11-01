"""Root wrapper for agent package."""
import os
import sys

# Ensure demo directory is in sys.path
demo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "demo"))
if demo_dir not in sys.path:
    sys.path.insert(0, demo_dir)

from demo.agent import *
