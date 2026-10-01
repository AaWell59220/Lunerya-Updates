from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ADMIN_PATH = "mods/LuneryaAdmin-1.21.1-3.0.0.jar"
ADMIN_URL = "https://github.com/AaWell59220/Lunerya-Updates/releases/download/lunerya-launcher-v1.0.42-assets/LuneryaAdmin-1.21.1-3.0.0.jar"

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--sha256", required=True)
    p.add_argument("--size", required=True, type=int)
    args = p.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if data.get("minecraft") != "1.21.1" or data.get("neoForge") != "21.1.244":
        raise SystemExit("Versions Minecraft/NeoForge inattendues.")

    files = data.get("files")
    if not isinstance(files, list):
        raise SystemExit("Manifeste invalide.")

    matches = [i for i, e in enumerate(files)
               if isinstance(e, dict) and str(e.get("path", "")).lower().startswith("mods/luneryaadmin-")]
    if len(matches) != 1:
        raise SystemExit(f"Il faut exactement une entree LuneryaAdmin, trouve: {len(matches)}")

    files[matches[0]] = {
        "path": ADMIN_PATH,
        "url": ADMIN_URL,
        "sha256": args.sha256.lower(),
        "size": args.size,
        "required": True,
    }
    data["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    args.manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
