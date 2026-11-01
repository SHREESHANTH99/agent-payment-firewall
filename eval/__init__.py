"""Root wrapper for eval package."""
import os
import sys

demo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "demo"))
if demo_dir not in sys.path:
    sys.path.insert(0, demo_dir)

from demo.eval import *
