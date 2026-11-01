"""Root CLI entrypoint forwarding to demo.eval.run_eval."""
import asyncio
import os
import sys

demo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "demo"))
if demo_dir not in sys.path:
    sys.path.insert(0, demo_dir)

from demo.eval.run_eval import main

if __name__ == "__main__":
    asyncio.run(main())
