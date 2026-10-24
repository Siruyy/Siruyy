"""Render assets/header.svg from the template, filling in uptime (age in whole years).

The birth date is read from the BIRTHDAY environment variable (YYYY-MM-DD), stored as a
repository secret, so it never appears in the public repo.
"""
import os
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "assets" / "header.template.svg"
OUTPUT = ROOT / "assets" / "header.svg"


def age_years(born: date, today: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def main() -> None:
    raw = os.environ.get("BIRTHDAY", "").strip()
    if not raw:
        raise SystemExit("BIRTHDAY is not set (expected YYYY-MM-DD)")
    born = date.fromisoformat(raw)
    today = datetime.now(timezone.utc).date()
    svg = TEMPLATE.read_text(encoding="utf-8").replace("{{UPTIME}}", f"{age_years(born, today)} years")
    if "{{" in svg:
        raise SystemExit("unfilled placeholder left in header template")
    OUTPUT.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
