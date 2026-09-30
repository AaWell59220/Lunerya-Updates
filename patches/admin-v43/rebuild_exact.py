from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

BASE_SHA256 = "e7e877a8276e84d7389b49eb2f1ea917185769feab78e99345f0f8e1e7d6bf20"
BASE_SIZE = 281250708
PATCH_SHA256 = "1af4f128f413c7a847ed6ea7185734240f8d0922768464d08911b92399ed644a"
TARGET_SHA256 = "0395aa5928579385d8a958e57933364545f63d32f64289f1abc368cfc0e06d58"
TARGET_SIZE = 281268276

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if args.base.stat().st_size != BASE_SIZE or sha256_file(args.base) != BASE_SHA256:
        raise SystemExit("Refus: le JAR Admin de base n'est pas exactement la version ZonesTP attendue.")

    patch_bytes = args.patch.read_bytes()
    if sha256_bytes(patch_bytes) != PATCH_SHA256:
        raise SystemExit("Refus: patch Admin corrompu ou incomplet.")

    base_bytes = args.base.read_bytes()
    with zipfile.ZipFile(args.base, "r") as base_zip:
        infos = base_zip.infolist()
        starts = [info.header_offset for info in infos]
        records: dict[str, bytes] = {}
        for idx, info in enumerate(infos):
            start = starts[idx]
            end = starts[idx + 1] if idx + 1 < len(starts) else base_zip.start_dir
            records[info.filename] = base_bytes[start:end]

    with zipfile.ZipFile(io.BytesIO(patch_bytes), "r") as patch_zip:
        recipe = json.loads(patch_zip.read("recipe.json").decode("utf-8"))
        expected = {
            "base_sha256": BASE_SHA256,
            "base_size": BASE_SIZE,
            "target_sha256": TARGET_SHA256,
            "target_size": TARGET_SIZE,
        }
        for key, value in expected.items():
            if recipe.get(key) != value:
                raise SystemExit(f"Refus: recette inattendue pour {key}.")

        changed = {name: i for i, name in enumerate(recipe["changed"])}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("wb") as out:
            for name in recipe["order"]:
                if name in changed:
                    out.write(patch_zip.read(f"records/{changed[name]:03d}.bin"))
                else:
                    if name not in records:
                        raise SystemExit(f"Entree de base manquante: {name}")
                    out.write(records[name])
            out.write(patch_zip.read("central.bin"))

    if args.out.stat().st_size != TARGET_SIZE or sha256_file(args.out) != TARGET_SHA256:
        raise SystemExit("Refus: le JAR reconstruit ne correspond pas octet pour octet au JAR fourni.")

    with zipfile.ZipFile(args.out, "r") as result:
        bad = result.testzip()
        if bad is not None:
            raise SystemExit(f"Archive JAR invalide: {bad}")
        required = {
            "fr/lunerya/adminmod/LuneryaShopRewards.class",
            "fr/lunerya/adminmod/LuneryaAdminScreenV3.class",
            "META-INF/neoforge.mods.toml",
        }
        names = set(result.namelist())
        missing = required - names
        if missing:
            raise SystemExit("Classes attendues absentes: " + ", ".join(sorted(missing)))

    print(f"JAR exact reconstruit: {args.out} ({TARGET_SIZE} octets, SHA-256 {TARGET_SHA256})")

if __name__ == "__main__":
    main()
