#!/usr/bin/env python3
"""Keeps PhotoDesigner's PWA install/update machinery honest on every commit.

Three independent things this does, all driven by content hashes so nothing
has to be hand-bumped:

1. Stamps manifest.json's icon `src` URLs, and index.html's
   `apple-touch-icon` `href`, with a content-hash query string whenever
   icon-192.png/icon-512.png change.

   Android/Chrome's installed-PWA (WebAPK) icon-update check only re-fetches
   an icon when its URL in the manifest changes -- it diffs the icons array's
   URLs, not pixel bytes -- and an Android uninstall does NOT clear Chrome's
   own service-worker/cache storage for the origin. So overwriting
   icon-192.png/icon-512.png in place would never be noticed by an existing
   install, or even by a fresh "Add to Home Screen" after an uninstall.
   Appending a content hash to the src/href query string gives every icon
   change a new URL, which is what actually triggers Chrome to pick it up.

   iOS Safari doesn't read manifest.json's icons array at all -- it uses the
   apple-touch-icon <link> tag in index.html's <head> -- so that tag needs the
   identical treatment, from the same hash, or iPhone's Home Screen icon goes
   stale even after Android's updates correctly.

2. Derives sw.js's CACHE_NAME from a content hash of every file in
   PRECACHE_URLS plus sw.js's own fetch-handling code (excluding the
   CACHE_NAME line itself, to avoid a self-referential hash). This guarantees
   the service worker's script bytes change on ANY precached-file edit --
   index.html, manifest.json, icons -- which is what lets checkForUpdate()'s
   reg.update() call actually detect the change instead of waiting on the
   browser's own lazy up-to-24h schedule.

3. Derives APP_VERSION (shown in the About popup) in index.html from a
   content hash of index.html itself (with the APP_VERSION line blanked, to
   avoid self-reference) plus manifest.json and the icon files. This is what
   makes the version marker actually change on every real code change,
   instead of sitting frozen at whatever it was hand-set to once -- it can't
   be used to confirm a reload picked up the latest deploy otherwise.

Run automatically by the pre-commit hook (.githooks/pre-commit). Safe to run
manually too -- it's a no-op if nothing precached has actually changed.
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "manifest.json"
INDEX_PATH = ROOT / "index.html"
SW_PATH = ROOT / "sw.js"

APP_VERSION_RE = re.compile(r"const APP_VERSION = '[^']*';")


def digest_for(rel_path):
    file_path = ROOT / rel_path
    if not file_path.is_file():
        sys.exit(f"missing file referenced by manifest.json/index.html/sw.js: {rel_path}")
    return hashlib.sha256(file_path.read_bytes()).hexdigest()[:8]


def sync_icon_versions():
    changed_paths = []

    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")

    def replace_manifest_src(m):
        rel_path = m.group(1)
        return f'"src": "{rel_path}?v={digest_for(rel_path)}"'

    new_manifest_text = re.sub(
        r'"src":\s*"(icon-(?:192|512)\.png)(?:\?v=[0-9a-f]+)?"',
        replace_manifest_src,
        manifest_text,
    )
    if new_manifest_text != manifest_text:
        MANIFEST_PATH.write_text(new_manifest_text, encoding="utf-8")
        changed_paths.append(MANIFEST_PATH)

    # index.html's apple-touch-icon isn't read from manifest.json by iOS
    # Safari, so it needs the same content-hash stamp kept in sync
    # separately -- see the module docstring.
    index_text = INDEX_PATH.read_text(encoding="utf-8")

    def replace_apple_touch_icon(m):
        rel_path = m.group(1)
        return f'<link rel="apple-touch-icon" href="./{rel_path}?v={digest_for(rel_path)}">'

    new_index_text = re.sub(
        r'<link rel="apple-touch-icon" href="\./(icon-192\.png)(?:\?v=[0-9a-f]+)?">',
        replace_apple_touch_icon,
        index_text,
    )
    if new_index_text != index_text:
        INDEX_PATH.write_text(new_index_text, encoding="utf-8")
        changed_paths.append(INDEX_PATH)

    return changed_paths


def sync_cache_name():
    sw_text = SW_PATH.read_text(encoding="utf-8")

    match = re.search(r"const PRECACHE_URLS = \[(.*?)\];", sw_text, re.S)
    if not match:
        sys.exit("Could not find PRECACHE_URLS array in sw.js")

    # Quote-agnostic on purpose -- a real bug found and fixed in LocalWork
    # (2026-08-25) had this hardcoded to double quotes while the array it was
    # parsing used single quotes, so it silently matched zero files and the
    # resulting hash never actually reacted to real precached-file edits.
    rel_paths = [p.lstrip("./") for p in re.findall(r'[\'"]([^\'"]+)[\'"]', match.group(1)) if p]
    if not rel_paths:
        sys.exit("PRECACHE_URLS parsed to zero files -- regex/quote-style mismatch, cache-name hashing would silently no-op")

    hasher = hashlib.sha256()
    for rel_path in rel_paths:
        file_path = ROOT / rel_path
        if not file_path.is_file():
            sys.exit(f"PRECACHE_URLS references missing file: {rel_path}")
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(file_path.read_bytes())

    # Include sw.js's own fetch-handling code (not just what it precaches) --
    # a bug in the fetch handler can write bad data into the cache under the
    # existing CACHE_NAME, and fixing the handler doesn't retroactively repair
    # whatever an already-affected device has sitting in that cache -- only a
    # fresh cache name does, via the normal old-cache-gets-deleted-on-activate
    # path in sw.js's 'activate' handler.
    sw_logic = re.sub(r"const CACHE_NAME = '[^']*';", "", sw_text)
    hasher.update(sw_logic.encode("utf-8"))

    new_name = f"photodesigner-shell-{hasher.hexdigest()[:12]}"

    new_sw_text, count = re.subn(
        r"const CACHE_NAME = '[^']*';",
        f"const CACHE_NAME = '{new_name}';",
        sw_text,
        count=1,
    )
    if count == 0:
        sys.exit("Could not find CACHE_NAME assignment in sw.js")

    if new_sw_text == sw_text:
        return None

    SW_PATH.write_text(new_sw_text, encoding="utf-8")
    return new_name


def sync_app_version():
    index_text = INDEX_PATH.read_text(encoding="utf-8")
    if not APP_VERSION_RE.search(index_text):
        sys.exit("Could not find APP_VERSION assignment in index.html")

    # Blank the version line itself before hashing index.html's own bytes, so
    # this isn't self-referential (a version derived from its own previous
    # value would never settle).
    blanked = APP_VERSION_RE.sub("const APP_VERSION = '';", index_text)

    hasher = hashlib.sha256()
    hasher.update(blanked.encode("utf-8"))
    hasher.update(MANIFEST_PATH.read_bytes())
    for rel_path in ("icon-192.png", "icon-512.png"):
        hasher.update((ROOT / rel_path).read_bytes())

    new_version = f"1.0+{hasher.hexdigest()[:8]}"
    new_index_text = APP_VERSION_RE.sub(f"const APP_VERSION = '{new_version}';", index_text, count=1)

    if new_index_text == index_text:
        return None

    INDEX_PATH.write_text(new_index_text, encoding="utf-8")
    return new_version


def main():
    changed_paths = set(sync_icon_versions())

    # Run before sync_cache_name(): CACHE_NAME's hash includes index.html's
    # bytes (via PRECACHE_URLS), so APP_VERSION must be finalized first --
    # otherwise CACHE_NAME converges to a stale value and needs a second
    # pass to catch up once APP_VERSION's own edit changes index.html again.
    new_version = sync_app_version()
    if new_version:
        changed_paths.add(INDEX_PATH)
        print(f"APP_VERSION updated -> {new_version}")

    new_cache_name = sync_cache_name()
    if new_cache_name:
        changed_paths.add(SW_PATH)
        print(f"CACHE_NAME updated -> {new_cache_name}")

    if not changed_paths:
        print("manifest.json/index.html/sw.js already up to date")
        return

    subprocess.run(["git", "add", *[str(p) for p in changed_paths]], cwd=ROOT, check=True)
    print(f"updated: {', '.join(sorted(p.name for p in changed_paths))}")


if __name__ == "__main__":
    main()
