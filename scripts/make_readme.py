"""Regenerate README.md with counts computed from the corpus on disk."""
import collections
import datetime
import json
import os
import re

from common import RAW, ROOT

LABELS = {
    "public": "Public Acts",
    "local": "Local Acts",
    "private": "Private Acts",
    "provincial": "Provincial Acts (Provincial Council ordinances/acts)",
    "imperial": "Imperial Acts (UK Acts in force in NZ)",
}


def count(dirpath):
    n = 0
    for _, _, files in os.walk(dirpath):
        n += sum(1 for f in files if f.endswith(".md") and f != "README.md")
    return n


def archive_range(dirpath):
    dates = []
    for d, _, files in os.walk(dirpath):
        for f in files:
            if not f.endswith(".md"):
                continue
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                head = fh.read(3000)
            m = re.search(r"^archived: '?(\d{4}-\d{2}-\d{2})", head, re.M)
            if m:
                dates.append(m.group(1))
    dates.sort()
    return (dates[0], dates[len(dates) // 2], dates[-1]) if dates else ("", "", "")


def main():
    rows = []
    total = 0
    for sub, label in LABELS.items():
        n = count(os.path.join(ROOT, "acts", sub))
        if n:
            rows.append(f"| {label} | `acts/{sub}/<year>/` | {n:,} |")
            total += n
    nsec = count(os.path.join(ROOT, "secondary"))
    if nsec:
        rows.append(f"| Secondary legislation (PCO-drafted regulations etc.) | `secondary/<year>/` | {nsec:,} |")
    ncon = count(os.path.join(ROOT, "constitution"))
    rows.append(f"| Treaty of Waitangi / Te Tiriti o Waitangi | `constitution/` | {ncon} |")
    lo, med, hi = archive_range(ROOT)
    skipped = collections.Counter()
    failed = 0
    report_path = os.path.join(RAW, "build_report.json")
    if os.path.exists(report_path):
        rep = json.load(open(report_path))
        for v in rep.values():
            if "skipped" in v:
                skipped[v["skipped"]] += 1
    fpath = os.path.join(RAW, "fetch_failed.json")
    if os.path.exists(fpath):
        failed = len(json.load(open(fpath)))
    skipped_txt = ", ".join(f"{n:,} {k}" for k, n in skipped.most_common()) or "none"
    tmpl = open(os.path.join(ROOT, "scripts", "README.template.md"), encoding="utf-8").read()
    out = tmpl.format(
        table="\n".join(rows),
        total=total + nsec,
        archived_lo=lo, archived_med=med, archived_hi=hi,
        skipped=skipped_txt, failed=failed,
        date=datetime.date.today().isoformat(),
    )
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(out)


if __name__ == "__main__":
    main()
