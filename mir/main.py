import os
import sys

__version__ = "0.1.0a12"

# Ensure parent directory of 'mir' is in path so absolute imports function correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mir.engine.config import load_config
from mir.engine.runner import run_linter

def main():
    try:
        config = load_config()
        exit_code = run_linter(config)
        sys.exit(exit_code)
    except Exception as e:
        print(f"Internal Error: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
