#!/usr/bin/env python3
"""Restore hash-verified binary sources from this repository's pinned Release."""
import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive-dir', type=Path, help='Use already downloaded Release parts, with no network calls')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'data/binary_assets.json').read_text())
    cache = ROOT/'.asset-cache'; cache.mkdir(exist_ok=True)
    by_digest = {}
    for item in manifest['files']:
        destination = ROOT/item['path']
        if not destination.resolve().is_relative_to(ROOT.resolve()): raise ValueError('Unsafe destination')
        by_digest.setdefault(item['sha256'], []).append(destination)
    restored = 0
    for part in manifest['archives']:
        needed = {d for d in part['objects'] if any(not p.is_file() or sha(p) != d for p in by_digest[d])}
        if not needed:
            print(f"Already complete: {part['name']}", flush=True); continue
        archive = (args.archive_dir if args.archive_dir else cache)/part['name']
        if not archive.is_file() or sha(archive) != part['sha256']:
            if args.archive_dir: raise ValueError(f'Missing or damaged local archive: {archive}')
            url = manifest['release_url']+'/'+part['name']
            print(f'Downloading {part["name"]} ({part["bytes"]:,} bytes)', flush=True)
            temp = archive.with_suffix('.partial')
            request = urllib.request.Request(url, headers={'User-Agent':'peer-review-benchmark-assets/0.1'})
            with urllib.request.urlopen(request, timeout=120) as response, temp.open('wb') as out:
                shutil.copyfileobj(response, out)
            if sha(temp) != part['sha256']:
                temp.unlink(); raise ValueError(f'Archive checksum failed: {part["name"]}')
            temp.replace(archive)
        with tarfile.open(archive, 'r:gz') as tar:
            seen=set()
            for member in tar:
                name=member.name
                if not member.isfile() or name not in part['objects'] or name in seen:
                    raise ValueError('Unexpected archive member')
                seen.add(name)
                if name not in needed: continue
                obj=cache/(name+'.object')
                with tar.extractfile(member) as src, obj.open('wb') as out: shutil.copyfileobj(src,out)
                if sha(obj) != name: raise ValueError('Object checksum failed')
                for dest in by_digest[name]:
                    if dest.is_file() and sha(dest)==name: continue
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    temp=dest.with_name(dest.name+'.restore-partial')
                    shutil.copyfile(obj,temp); temp.replace(dest); restored+=1
                obj.unlink()
            if seen != set(part['objects']): raise ValueError('Incomplete archive')
    for digest,paths in by_digest.items():
        if any(not p.is_file() or sha(p)!=digest for p in paths): raise ValueError('Incomplete restoration')
    print(f"Complete: {len(manifest['files'])} binary paths verified; {restored} restored. No models called.")

if __name__ == '__main__': main()
