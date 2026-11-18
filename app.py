"""Vercel entrypoint: Vercel serves the ASGI object named `app` from this file."""

import sys
from pathlib import Path

# The package lives in src/; make it importable even if the platform does not install it.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lexcrawl_dashboard.web.app import create_app

app = create_app()
