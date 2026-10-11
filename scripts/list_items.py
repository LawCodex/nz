"""Enumerate archived legislation.govt.nz "whole" pages via the Wayback Machine CDX API.

legislation.govt.nz (since its 2026 relaunch) sits behind an AWS WAF JavaScript challenge and
its API needs a key issued on request by the PCO, so the corpus is rebuilt from the Internet
Archive's captures of the official site's classic "whole.html" pages
(https://www.legislation.govt.nz/act/<subtype>/<year>/<number>/latest/whole.html).

For every (kind, subtype, year, number) the most recent HTTP-200 capture of the
.../latest/whole.html page is kept. Output: _raw/nz/index.json
"""
import argparse
import os
import re
import sys

from common import RAW, WAYBACK, get, read_json, write_json

KINDS = {
    "act": ["public", "local", "private", "provincial", "imperial"],
    "regulation": ["public"],
}
# classic site:  /act/public/1990/0109/latest/whole.html
# current site:  /act/public/1990/109/en/latest/
URL_RE = re.compile(
    r"^https?://(?:www\.)?legislation\.govt\.nz/(act|regulation)/(\w+)/(\d{4})/0*(\d+[a-z]?)/"
    r"(latest/whole\.html|en/latest/?)$",
    re.I,
)
SMALL = {"provincial", "imperial"}  # queried in one go


def cdx(prefix, tries=7, timeout=600):
    params = {
        "url": f"legislation.govt.nz/{prefix}",
        "matchType": "prefix",
        "filter": ["statuscode:200", r"original:.*(/latest/whole\.html|/en/latest/?)"],
        "fl": "original,timestamp,length,digest",
    }
    r = get(f"{WAYBACK}/cdx/search/cdx", params=params, timeout=timeout, tries=tries)
    return [] if r is None else r.text.splitlines()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", default="act", help="comma list: act,regulation")
    args = ap.parse_args()
    cache_dir = os.path.join(RAW, "cdx2")
    os.makedirs(cache_dir, exist_ok=True)
    out_path = os.path.join(RAW, "index.json")
    for kind in args.kinds.split(","):
        for sub in KINDS[kind]:
            for dec in ([""] if sub in SMALL else range(184, 203)):
                prefix = f"{kind}/{sub}/{dec}"
                cpath = os.path.join(cache_dir, prefix.replace("/", "_") + ".txt")
                if not os.path.exists(cpath):
                    try:
                        lines = cdx(prefix, tries=2, timeout=150)
                    except RuntimeError:
                        # large decade: query year by year
                        lines = []
                        for y in range(10):
                            lines += cdx(f"{prefix}{y}/")
                    with open(cpath + ".tmp", "w", encoding="utf-8") as f:
                        f.write("\n".join(lines))
                    os.replace(cpath + ".tmp", cpath)
                    print(f"{prefix}: {len(lines)} captures", file=sys.stderr)
    # (re)build the index from every cached CDX listing
    index = {}
    for fn in sorted(os.listdir(cache_dir)):
        if not fn.endswith(".txt"):
            continue
        for line in open(os.path.join(cache_dir, fn), encoding="utf-8"):
            parts = line.split()
            if len(parts) < 3:
                continue
            m = URL_RE.match(parts[0])
            if not m:
                continue
            k, s, y, num, style = m.groups()
            key = f"{k}/{s.lower()}/{y}/{int(num[:-1] if num[-1].isalpha() else num):04d}{num[-1] if num[-1].isalpha() else ''}"
            caps = index.setdefault(key, {"captures": []})["captures"]
            if [parts[1], parts[0]] not in caps:
                caps.append([parts[1], parts[0]])
    for v in index.values():
        v["captures"].sort(reverse=True)
        del v["captures"][8:]
    write_json(out_path, index)
    print(f"{len(index)} items", file=sys.stderr)


if __name__ == "__main__":
    main()
