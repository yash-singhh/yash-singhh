"""Package entry point — enables ``python -m social_analyzer``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
