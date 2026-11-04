#!/usr/bin/env python3
"""Publish verified compiled Forgematica and MaFgLib without altering other Lunerya mods."""
from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile, BadZipFile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(os.environ.get("LUNERYA_LIVE_MANIFEST", ROOT / "site" / "manifest.json"))
VERSION = "0.4.3+mc1.21.1"
MODS = (
    ("forgematica", "dCKRaeBC", "forgematica"),
    ("mafglib", "SKI34J7B", "mafglib"),
)


def read_url(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Lunerya-Launcher-Publisher/1.0 (GitHub Actions)"})
    with urlopen(request, timeout=45) as response:
        return response.read()


def fetch_mod(project_id: str, prefix: str, modid: str) -> dict:
    # Only fetch the verified compiled release for NeoForge 1.21.1.
    query = "?loaders=%5B%22neoforge%22%5D&game_versions=%5B%221.21.1%22%5D"
    versions = json.loads(read_url(f"https://api.modrinth.com/v2/project/{project_id}/version{query}"))
    candidates = [
        item for item in versions
        if item.get("version_number") == VERSION
        and "neoforge" in item.get("loaders", [])
        and "1.21.1" in item.get("game_versions", [])
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one NeoForge 1.21.1 release for {prefix} {VERSION}; got {len(candidates)}")
    release = candidates[0]
    filename = f"{prefix}-{VERSION}.jar"
    binaries = [file for file in release.get("files", []) if file.get("filename") == filename]
    if len(binaries) != 1:
        raise RuntimeError(f"Missing compiled {filename}")
    binary = binaries[0]
    url = binary.get("url", "")
    if urlparse(url).scheme != "https" or urlparse(url).hostname != "cdn.modrinth.com":
        raise RuntimeError(f"Untrusted download URL for {filename}")
    payload = read_url(url)
    digest = hashlib.sha256(payload).hexdigest()
    # Modrinth publishes SHA-512/SHA-1; Lunerya needs a verified SHA-256.
    hashes = binary.get("hashes", {})
    if not hashes.get("sha512"):
        raise RuntimeError(f"Missing SHA512 from Modrinth for {filename}")
    if hashlib.sha512(payload).hexdigest() != hashes["sha512"].lower():
        raise RuntimeError(f"SHA512 mismatch for {filename}")
    if hashes.get("sha1") and hashlib.sha1(payload).hexdigest() != hashes["sha1"].lower():
        raise RuntimeError(f"SHA1 mismatch for {filename}")
    if len(payload) < 100_000:
        raise RuntimeError(f"Unexpectedly small JAR: {filename}")
    try:
        with ZipFile(io.BytesIO(payload)) as z:
            names = z.namelist()
            if "META-INF/neoforge.mods.toml" not in names:
                raise RuntimeError(f"No NeoForge metadata in {filename}")
            if sum(name.endswith(".class") for name in names) < 10:
                raise RuntimeError(f"Source JAR instead of compiled JAR: {filename}")
            toml = z.read("META-INF/neoforge.mods.toml").decode("utf-8")
            if f'modId="{modid}"' not in toml:
                raise RuntimeError(f"Wrong mod ID in {filename}")
    except BadZipFile as exc:
        raise RuntimeError(f"Invalid JAR: {filename}") from exc
    print(f"Verified {filename}: {len(payload)} bytes, sha256:{digest}")
    return {"path": "mods/" + filename, "url": url, "sha256": digest, "size": len(payload), "required": True}


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1 or data.get("minecraft") != "1.21.1" or data.get("neoForge") != "21.1.248":
        raise RuntimeError("Unexpected manifest schema or Minecraft/NeoForge version")
    files = data.get("files")
    if not isinstance(files, list) or len(files) < 10:
        raise RuntimeError("Incomplete live manifest: refusing deployment")
    paths = [file.get("path") for file in files]
    if len(set(paths)) != len(paths):
        raise RuntimeError("Existing duplicate manifest entries")
    managed = ("mods/forgematica-", "mods/mafglib-")
    untouched = [entry for entry in files if not entry["path"].lower().startswith(managed)]
    new_entries = [fetch_mod(project, prefix, modid) for prefix, project, modid in MODS]
    data["files"] = untouched + new_entries
    if data["files"][:-2] != untouched or len({entry["path"] for entry in data["files"]}) != len(data["files"]):
        raise RuntimeError("Manifest validation failed")
    data["generatedAt"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    temporary = MANIFEST.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(MANIFEST)
    print(f"Manifest verified: {len(data['files'])} files; existing Lunerya files preserved")


if __name__ == "__main__":
    main()
