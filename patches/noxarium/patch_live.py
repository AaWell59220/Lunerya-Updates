#!/usr/bin/env python3
"""Patch only Lunerya display names in the current published premium mod."""
import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_HASH = '6ffaf64a43dbc2c09a83e5e0877e069ea2e8a8fa84506ddeb4b805ec64e5622b'
EXPECTED_SIZE = 28280573
MOD_PATH = 'mods/lunerya-0.1.0.jar'
REQUIRED_ASSETS = (
    'assets/lunerya/textures/gui/v26/background_4k.png',
    'assets/lunerya/textures/gui/v26/logo.png',
    'assets/lunerya/textures/gui/v26/play.png',
    'assets/lunerya/textures/gui/v26/options.png',
    'assets/lunerya/textures/gui/v26/discord.png',
    'assets/lunerya/textures/gui/v26/quit.png',
    'assets/lunerya/textures/gui/v27/menu_exact_4k.png',
    'assets/lunerya/textures/gui/v28/background.png',
    'assets/lunerya/textures/gui/v28/logo.png',
    'assets/lunerya/textures/gui/v28/play.png',
    'assets/lunerya/textures/gui/v28/options.png',
    'assets/lunerya/textures/gui/v28/discord.png',
    'assets/lunerya/textures/gui/v28/quit.png',
    'assets/lunerya/textures/gui/v35/options_ui.png',
)
TARGET_KEYS = (
    'block.lunerya.luneryum_ore.deepslate',
    'item.lunerya.raw_luneryum',
    'item.lunerya.seigneur_lunaire_chestplate',
    'item.lunerya.seigneur_lunaire_leggings',
    'item.lunerya.seigneur_lunaire_boots',
    'item.lunerya.seigneur_lunaire_hoe',
    'item.lunerya.seigneur_lunaire_pickaxe',
    'item.lunerya.seigneur_lunaire_shovel',
    'item.lunerya.seigneur_lunaire_helmet',
    'item.lunerya.seigneur_lunaire_sword',
    'item.lunerya.seigneur_lunaire_axe',
    'block.lunerya.luneryum_block',
    'block.lunerya.luneryum_ore',
    'item.lunerya.luneryum_block',
    'item.lunerya.luneryum_ore',
    'item.lunerya.seigneur_lunaire_ingot',
)
SPECIAL = {
    'fr_fr': {
        'item.lunerya.lunerya_fragment': 'Fragment de Luneryum',
        'item.lunerya.lunerya_ingot': 'Lingot de Luneryum',
    },
    'en_us': {
        'item.lunerya.lunerya_fragment': 'Luneryum Fragment',
        'item.lunerya.lunerya_ingot': 'Luneryum Ingot',
    },
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def patch_lang(raw, locale):
    data = json.loads(raw.decode('utf-8-sig'))
    required = set(TARGET_KEYS) | set(SPECIAL[locale]) | {'item.lunerya.lunerya_sword'}
    missing = required - data.keys()
    if missing:
        raise RuntimeError(f'Missing required {locale} keys: {sorted(missing)}')
    old_sword = data['item.lunerya.lunerya_sword']
    changed = []
    for key in TARGET_KEYS:
        value = data[key]
        if not isinstance(value, str) or ('Luneryum' not in value and 'Noxarium' not in value):
            raise RuntimeError(f'Unexpected value for {locale} {key}: {value!r}')
        updated = value.replace('Luneryum', 'Noxarium')
        if updated != value:
            data[key] = updated
            changed.append(key)
    for key, name in SPECIAL[locale].items():
        if not isinstance(data[key], str) or not any(
            w in data[key].lower() for w in ('eclipse', 'éclipse', 'luneryum')
        ):
            raise RuntimeError(f'Unexpected {locale} resource name: {key} = {data[key]!r}')
        if data[key] != name:
            data[key] = name
            changed.append(key)
    if data['item.lunerya.lunerya_sword'] != old_sword:
        raise RuntimeError('Eclipse sword renamed unexpectedly')
    if not changed:
        raise RuntimeError(f'Nothing to patch in {locale}; refusing no-op publish')
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'), changed

def main(site):
    site = Path(site).resolve()
    manifest_path = site / 'manifest.json'
    jar_path = site / 'files' / MOD_PATH
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    matches = [f for f in manifest.get('files', []) if f.get('path') == MOD_PATH]
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one Lunerya mod manifest entry')
    entry = matches[0]
    if entry.get('sha256') != EXPECTED_HASH or entry.get('size') != EXPECTED_SIZE:
        raise RuntimeError('Published manifest changed; abort to preserve current release')
    jar_bytes = jar_path.read_bytes()
    if digest(jar_bytes) != EXPECTED_HASH or len(jar_bytes) != EXPECTED_SIZE:
        raise RuntimeError('Published JAR differs from manifest; abort')
    updates = {}
    with zipfile.ZipFile(jar_path, 'r') as source:
        names = source.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError('Duplicate JAR entries; abort')
        missing_assets = set(REQUIRED_ASSETS) - set(names)
        if missing_assets:
            raise RuntimeError(f'Premium menu assets missing: {sorted(missing_assets)}')
        if any(n.startswith('META-INF/') and n.upper().endswith(('.SF', '.RSA', '.DSA', '.EC')) for n in names):
            raise RuntimeError('Signed JAR; rewriting requires re-signing')
        metadata = source.read('META-INF/neoforge.mods.toml').decode('utf-8')
        if 'modId="lunerya"' not in metadata or 'version="0.1.0"' not in metadata:
            raise RuntimeError('Unexpected mod identity/version')
        for locale in SPECIAL:
            name = f'assets/lunerya/lang/{locale}.json'
            updated, changes = patch_lang(source.read(name), locale)
            updates[name] = updated
            print(f'{locale}: {len(changes)} names updated: {", ".join(changes)}')
        original_hashes = {
            name: digest(source.read(name))
            for name in names if name not in updates and not name.endswith('/')
        }
        fd, temp_path = tempfile.mkstemp(prefix='lunerya-noxarium-', suffix='.jar', dir=jar_path.parent)
        os.close(fd)
        try:
            with zipfile.ZipFile(temp_path, 'w') as target:
                target.comment = source.comment
                for info in source.infolist():
                    target.writestr(info, updates.get(info.filename, source.read(info.filename)))
            with zipfile.ZipFile(temp_path) as check:
                if set(check.namelist()) != set(names):
                    raise RuntimeError('Archive entries changed')
                for name, old_hash in original_hashes.items():
                    if digest(check.read(name)) != old_hash:
                        raise RuntimeError(f'Existing mod content changed: {name}')
                for name, updated in updates.items():
                    if check.read(name) != updated:
                        raise RuntimeError(f'Language patch failed: {name}')
            new_bytes = Path(temp_path).read_bytes()
            new_hash = digest(new_bytes)
            if new_hash == EXPECTED_HASH:
                raise RuntimeError('Unexpected unchanged mod hash')
            os.replace(temp_path, jar_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    entry['sha256'] = new_hash
    entry['size'] = len(new_bytes)
    manifest['generatedAt'] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'SUCCESS: updated mod SHA256={new_hash}, size={len(new_bytes)}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', required=True)
    args = parser.parse_args()
    main(args.site)
