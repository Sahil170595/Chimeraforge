from __future__ import annotations

import json
from pathlib import Path
import platform
import sys

from banterhearts.runtime.capabilities import detect_capabilities


def main() -> None:
    caps = detect_capabilities().to_dict()
    env = {
        "platform": platform.platform(),
        "python": sys.version,
        "caps": caps,
    }
    out = Path("results/tr117/env.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(env, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
