#!/usr/bin/env python3
"""Export OpenAPI schema from the Ghost Backend API.

Usage:
    python tools/scripts/export_openapi.py [output_path]

Default output: docs/openapi.json
"""

import json
import sys
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ghost.config import Config, set_config
from ghost.api import APIManager


def main():
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/openapi.json")

    # Use a minimal config so we don't need env vars / DB
    config = Config(environment="development")
    set_config(config)

    api_manager = APIManager(config.api)
    app = api_manager.create_app(
        title=config.project_name,
        description="Ghost Backend API",
        version=config.version,
    )

    schema = app.openapi()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)

    print(f"OpenAPI schema exported to {output_path}")


if __name__ == "__main__":
    main()
