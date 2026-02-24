"""Buffer sync CLI — flush local telemetry buffer to DynamoDB.

Usage:
    poetry run python -m assemblyzero.telemetry.sync
"""

import sys

from assemblyzero.telemetry.emitter import flush


def main() -> None:
    """Flush local buffer and report count."""
    count = flush()
    if count > 0:
        print(f"Synced {count} buffered event(s) to DynamoDB.")
    else:
        print("No buffered events to sync.")


if __name__ == "__main__":
    main()
