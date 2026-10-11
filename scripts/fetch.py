"""Download the archived whole.html captures listed in _raw/nz/index.json (from list_items.py).

Captures are fetched raw (Wayback "id_" mode) and cached gzip-compressed under
_raw/nz/html/<kind>/<subtype>/<year>/<number>.html.gz. The most recent capture is tried first;
if it is not a usable legislation page, older captures are tried.
"""
import argparse
import gzip
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import RAW, WAYBACK, get, read_json, write_json


def cache_path(key):
    return os.path.join(RAW, "html", key + ".html.gz")


def fetch_one(key, item):
    path = cache_path(key)
    if os.path.exists(path):
        return key, "cached", None
    last = None
    for ts, url in item["captures"]:
        try:
            r = get(f"{WAYBACK}/web/{ts}id_/{url}")
        except RuntimeError as e:
            last = str(e)
            continue
        if r is None:
            last = "404"
            continue
        data = r.content
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        if b'id="legislation"' not in data and b'class="act"' not in data:
            last = "not a legislation page"
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with gzip.open(path + ".tmp", "wb") as f:
            f.write(data)
        os.replace(path + ".tmp", path)
        with open(path[:-8] + ".capture", "w") as f:
            f.write(f"{ts} {url}\n")
        return key, "ok", None
    return key, "failed", last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--prefix", default="", help="only keys starting with this, e.g. act/public")
    args = ap.parse_args()
    index = read_json(os.path.join(RAW, "index.json"))
    keys = sorted(k for k in index if k.startswith(args.prefix))
    todo = [k for k in keys if not os.path.exists(cache_path(k))]
    print(f"{len(keys)} items, {len(todo)} to fetch", file=sys.stderr)
    failed = {}
    done = 0
    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(fetch_one, k, index[k]) for k in todo]
        for fut in as_completed(futs):
            key, status, err = fut.result()
            done += 1
            if status == "failed":
                failed[key] = err
            if done % 100 == 0:
                print(f"{done}/{len(todo)} ({len(failed)} failed)", file=sys.stderr, flush=True)
    fpath = os.path.join(RAW, "fetch_failed.json")
    old = read_json(fpath) if os.path.exists(fpath) else {}
    old.update(failed)
    for k in list(old):
        if os.path.exists(cache_path(k)):
            del old[k]
    write_json(fpath, old)
    print(f"done; {len(failed)} failed", file=sys.stderr)


if __name__ == "__main__":
    main()
