from pathlib import Path
import json

def load_scan_schedule(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open('r') as f:
        return json.load(f)
