"""Convert the cached whole.html pages into the Markdown corpus.

acts/<subtype>/<year>/<year>-<number>-<slug>.md   (public, local, private, provincial, imperial)
secondary/<year>/<year>-<number>-<slug>.md        (PCO-drafted regulations, if fetched)
constitution/treaty-of-waitangi.md                (Schedule 1 of the Treaty of Waitangi Act 1975)

Only legislation not marked repealed/revoked/expired on its archived page is written.
Writes _raw/nz/build_report.json with counts and skipped items.
"""
import argparse
import datetime
import glob
import gzip
import os
import re
import shutil
import sys
import unicodedata

import yaml

from common import RAW, ROOT, write_json
from convert import convert, parse_date

TODAY = datetime.date.today().isoformat()
TYPE_DIR = {"act": "acts", "regulation": "secondary"}


def slugify(s, maxlen=80):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s or "untitled"


def fm(d):
    d = dict(d)
    for k in ("date", "last_amended", "archived", "retrieved"):
        v = d.get(k)
        if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            d[k] = datetime.date.fromisoformat(v)
    return "---\n" + yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=1000) + "---\n"


def out_path(kind, sub, year, num, title):
    numpart = num.lstrip("0") or "0"
    name = f"{year}-{numpart}-{slugify(title)}.md"
    if kind == "act":
        return os.path.join(ROOT, "acts", sub, year, name)
    return os.path.join(ROOT, "secondary", year, name)


def build_one(key, html_path):
    kind, sub, year, num = key.split("/")
    cap = open(html_path[:-8] + ".capture").read().split()
    ts, url = cap[0], cap[1]
    with gzip.open(html_path, "rb") as f:
        raw = f.read().decode("utf-8", "replace")
    meta, body = convert(raw, base_url=url)
    title = meta["title"] or re.sub(r"\s+\d{4} No \d+.*$", "", meta["page_title"])
    term = (meta.get("terminated") or "").lower()
    for b in meta.get("badges") or []:
        if b.lower() in ("repealed", "expired", "revoked", "spent", "lapsed"):
            term = b.lower()
    if term:
        return key, {"skipped": term, "title": title, "message": meta.get("alert_message", "")}, None
    status = "in_force"
    bl = [b.lower() for b in meta.get("badges") or []]
    if bl and "in force" not in bl:
        status = "unknown"
    numpart = num.lstrip("0") or "0"
    number = meta["number"]
    if not number:
        m = re.search(r"\b(\d{4}) No (\w+)", meta["page_title"])
        number = f"{m.group(1)} No {m.group(2)}" if m else f"{year} No {numpart}"
    version = parse_date(meta["version"]) or parse_date(
        (re.search(r"\(as at ([^)]*)\)", meta["page_title"]) or [None, ""])[1]) or parse_date(
        meta.get("banner_asat"))
    date = parse_date(meta["assent"]) or parse_date(meta["made"])
    doc_type = meta["doc_type"] or (meta["page_title"].rsplit(",", 1)[-1].split("–")[0].strip()
                                    if "," in meta["page_title"] else "")
    seg = "act" if kind == "act" else "secondary-legislation"
    subseg = sub if kind == "act" else "pco-drafted"
    front = {
        "title": title,
        "identifier": f"{seg}_{subseg}_{year}_{numpart}",
        "number": number,
        "type": "act" if kind == "act" else "regulation",
        "subtype": doc_type or f"{sub} {kind}",
        "jurisdiction": "nz",
        "language": "en",
        "date": date,
        "last_amended": version,
        "status": status,
        "source": f"https://www.legislation.govt.nz/{seg}/{subseg}/{year}/{numpart}/en/latest/",
        "archived_source": f"https://web.archive.org/web/{ts}/{url}",
        "archived": f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}",
        "retrieved": TODAY,
    }
    if meta["admin"].startswith("This "):
        front["administered_by"] = re.sub(r"^This \w+ is administered by (the )?|\.$", "", meta["admin"])
    front = {k: v for k, v in front.items() if v not in (None, "")}
    md = fm(front) + f"\n# {title}\n\n" + body + "\n"
    path = out_path(kind, sub, year, num, title)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    return key, {"path": os.path.relpath(path, ROOT), "title": title, "last_amended": version,
                 "archived": front["archived"]}, md


def treaty(md):
    """Extract Schedule 1 (Treaty of Waitangi, English and Maori texts) of the 1975 Act."""
    m = re.search(r"^## Schedule 1 The Treaty of Waitangi\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    if not m:
        return None
    fmd = re.search(r"^---\n(.*?)\n---\n", md, re.S)
    src = yaml.safe_load(fmd.group(1))
    body = m.group(1).strip()
    body = re.sub(r"^(#+) ", lambda x: "#" * max(2, len(x.group(1)) - 1) + " ", body, flags=re.M)
    front = {
        "title": "The Treaty of Waitangi / Te Tiriti o Waitangi",
        "identifier": "act_public_1975_114 Schedule 1",
        "type": "treaty",
        "jurisdiction": "nz",
        "language": "en, mi",
        "date": "1840-02-06",
        "last_amended": src.get("last_amended"),
        "status": "in_force",
        "source": src["source"],
        "archived_source": src["archived_source"],
        "retrieved": TODAY,
        "note": "Text as set out in Schedule 1 of the Treaty of Waitangi Act 1975 (English and Māori texts).",
    }
    return fm(front) + "\n# The Treaty of Waitangi / Te Tiriti o Waitangi\n\n" + body + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="", help="only keys starting with this, e.g. act/public")
    ap.add_argument("--clean", action="store_true", help="remove existing output dirs for the prefix first")
    args = ap.parse_args()
    files = sorted(glob.glob(os.path.join(RAW, "html", "**", "*.html.gz"), recursive=True))
    report_path = os.path.join(RAW, "build_report.json")
    report = {}
    if os.path.exists(report_path):
        import json
        report = json.load(open(report_path))
    if args.clean and args.prefix:
        kind, _, sub = args.prefix.partition("/")
        d = os.path.join(ROOT, TYPE_DIR[kind], sub) if sub and kind == "act" else os.path.join(ROOT, TYPE_DIR[kind])
        shutil.rmtree(d, ignore_errors=True)
    n = 0
    for p in files:
        key = os.path.relpath(p, os.path.join(RAW, "html"))[:-8]
        if not key.startswith(args.prefix):
            continue
        try:
            key, info, md = build_one(key, p)
        except Exception as e:  # noqa
            info, md = {"error": repr(e)}, None
            print(f"ERROR {key}: {e!r}", file=sys.stderr)
        report[key] = info
        if key == "act/public/1975/0114" and md:
            t = treaty(md)
            if t:
                os.makedirs(os.path.join(ROOT, "constitution"), exist_ok=True)
                with open(os.path.join(ROOT, "constitution", "treaty-of-waitangi.md"), "w",
                          encoding="utf-8", newline="\n") as f:
                    f.write(t)
        n += 1
        if n % 500 == 0:
            print(f"{n} converted", file=sys.stderr, flush=True)
    write_json(report_path, report)
    written = sum(1 for v in report.values() if "path" in v)
    skipped = sum(1 for v in report.values() if "skipped" in v)
    errors = sum(1 for v in report.values() if "error" in v)
    print(f"written {written}, skipped (repealed etc.) {skipped}, errors {errors}", file=sys.stderr)


if __name__ == "__main__":
    main()
