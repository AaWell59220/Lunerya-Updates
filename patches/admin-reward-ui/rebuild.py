from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

BASE_SHA256 = "0395aa5928579385d8a958e57933364545f63d32f64289f1abc368cfc0e06d58"
BASE_SIZE = 281268276
PATCH_SHA256 = "f2ee4353ee7f02cac5c3b7cae2f71e496947e7fae7e9a5254762a5adc9bdc1ec"

REQUIRED = {
    "fr/lunerya/adminmod/LuneryaShopRewards$Reward.class",
    "fr/lunerya/adminmod/LuneryaShopRewards$Store.class",
    "fr/lunerya/adminmod/LuneryaShopRewards.class",
    "fr/lunerya/adminmod/LuneryaRewardChestMenu.class",
    "fr/lunerya/adminmod/LuneryaRewardChestProvider.class",
    "fr/lunerya/adminmod/LuneryaRewardSilent.class",
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--patch", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()

    args.base = args.base.resolve()
    args.patch = args.patch.resolve()
    args.out = args.out.resolve()

    if args.base.stat().st_size != BASE_SIZE or sha256_file(args.base) != BASE_SHA256:
        raise SystemExit("Refus: le LuneryaAdmin public n'est plus la base verifiee.")
    if sha256_file(args.patch) != PATCH_SHA256:
        raise SystemExit("Refus: patch Reward UI incomplet ou corrompu.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.base, args.out)

    with zipfile.ZipFile(args.patch, "r") as patch_zip:
        meta = json.loads(patch_zip.read("patch-meta.json").decode("utf-8"))
        if meta.get("base_sha256") != BASE_SHA256 or meta.get("base_size") != BASE_SIZE:
            raise SystemExit("Refus: metadata du patch incoherente.")
        patch_names = set(patch_zip.namelist()) - {"patch-meta.json"}
        if patch_names != REQUIRED:
            raise SystemExit("Refus: liste de classes du patch inattendue.")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in sorted(REQUIRED):
                data = patch_zip.read(name)
                expected = meta["entries"][name]
                if len(data) != expected["size"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                    raise SystemExit("Refus: classe patch corrompue: " + name)
                out_file = root / name
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_bytes(data)

            cmd = ["zip", "-q", "-X", str(args.out)] + sorted(REQUIRED)
            subprocess.run(cmd, cwd=root, check=True)

    with zipfile.ZipFile(args.out, "r") as result:
        bad = result.testzip()
        if bad is not None:
            raise SystemExit("JAR final invalide: " + bad)
        names = result.namelist()
        if len(names) != len(set(names)):
            raise SystemExit("JAR final contient des entrees dupliquees.")
        if not REQUIRED.issubset(set(names)):
            raise SystemExit("Classes Reward UI manquantes.")
        if "META-INF/neoforge.mods.toml" not in names:
            raise SystemExit("neoforge.mods.toml absent.")
        for name in REQUIRED:
            data = result.read(name)
            expected = meta["entries"][name]
            if len(data) != expected["size"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise SystemExit("Verification finale echouee: " + name)

    print("FINAL_SHA256=" + sha256_file(args.out))
    print("FINAL_SIZE=" + str(args.out.stat().st_size))

if __name__ == "__main__":
    main()
