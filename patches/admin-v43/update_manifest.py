from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ADMIN_PATH = "mods/LuneryaAdmin-1.21.1-3.0.0.jar"
ADMIN_URL = "https://github.com/AaWell59220/Lunerya-Updates/releases/download/lunerya-launcher-v1.0.42-assets/LuneryaAdmin-1.21.1-3.0.0.jar"
ADMIN_SHA256 = "0395aa5928579385d8a958e57933364545f63d32f64289f1abc368cfc0e06d58"
ADMIN_SIZE = 281268276
OLD_SHA256 = "e7e877a8276e84d7389b49eb2f1ea917185769feab78e99345f0f8e1e7d6bf20"

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if data.get("minecraft") != "1.21.1" or data.get("neoForge") != "21.1.244":
        raise SystemExit("Versions Minecraft/NeoForge inattendues: publication refusee.")
    files = data.get("files")
    if not isinstance(files, list):
        raise SystemExit("Manifeste invalide: files absent.")

    indexes = [i for i, entry in enumerate(files)
               if isinstance(entry, dict) and str(entry.get("path", "")).lower().startswith("mods/luneryaadmin-")]
    if len(indexes) != 1:
        raise SystemExit(f"Il faut exactement une entree LuneryaAdmin, trouve: {len(indexes)}")

    current = files[indexes[0]]
    current_sha = str(current.get("sha256", "")).lower()
    if current_sha not in {OLD_SHA256, ADMIN_SHA256}:
        raise SystemExit("Le manifeste public a change depuis la verification: publication refusee.")

    target = {
        "path": ADMIN_PATH,
        "url": ADMIN_URL,
        "sha256": ADMIN_SHA256,
        "size": ADMIN_SIZE,
        "required": True,
    }
    if current == target:
        print("Manifest deja a jour.")
        return

    files[indexes[0]] = target
    data["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    args.manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    check = [e for e in data["files"] if str(e.get("path", "")).lower().startswith("mods/luneryaadmin-")]
    if len(check) != 1 or check[0] != target:
        raise SystemExit("Validation finale du manifeste echouee.")
    print("Manifest: LuneryaAdmin final reference une seule fois.")

if __name__ == "__main__":
    main()
