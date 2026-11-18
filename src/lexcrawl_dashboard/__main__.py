"""`lexcrawl-dashboard` / `python -m lexcrawl_dashboard`: serve the dashboard with uvicorn."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Run the app; HOST and PORT come from the environment (PORT is set by most hosts)."""
    uvicorn.run(
        "lexcrawl_dashboard.web.app:create_app",
        factory=True,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
