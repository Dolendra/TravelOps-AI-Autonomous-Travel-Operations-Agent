import json
import os
import sys

# Add the repository root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.api.main import app


def main():
    # Force generate openapi schema dictionary
    openapi_schema = app.openapi()

    target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    os.makedirs(target_dir, exist_ok=True)

    target_file = os.path.join(target_dir, "openapi.json")
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"[+] OpenAPI specification successfully written to {target_file}")


if __name__ == "__main__":
    main()
