# New Zealand legislation — LawCodex

The Acts of the New Zealand Parliament (and earlier legislatures) as plain Markdown, one file per
Act, part of [LawCodex](https://github.com/LawCodex).

**Jurisdiction:** New Zealand (`nz`) · **Language:** English (the Treaty of Waitangi schedule also
contains the Māori text) · **Generated:** {date}

> **Important — provenance and currency.** The official site, legislation.govt.nz, is now behind an
> AWS WAF JavaScript challenge, and its API (api.legislation.govt.nz) requires a personal API key
> issued on request by the Parliamentary Counsel Office. Neither was available to this build, so the
> texts were taken from **Internet Archive (Wayback Machine) captures of the official
> legislation.govt.nz pages**: the current site's `/act/<subtype>/<year>/<number>/en/latest/` page
> (which embeds the full PCO text) when archived, otherwise the classic site's
> `…/latest/whole.html` page. For each Act the most recent usable capture is used. Each file is the
> official PCO consolidation *as it stood when the page was archived*: the front matter records the
> consolidation date (`last_amended`), the capture date (`archived`) and the exact capture URL
> (`archived_source`). Captures range from {archived_lo} to {archived_hi} (median {archived_med});
> some older captures are stale, so amendments (or repeals) made after a file's `archived` date are
> **not** reflected. Always check the official version on
> [legislation.govt.nz](https://www.legislation.govt.nz) before relying on a text.

## What is covered

| Category | Directory | Files |
|---|---|---:|
{table}

Total: **{total:,}** Acts / instruments.

Only legislation that was **not** shown as repealed/expired on its archived page is included
(skipped as no longer in force: {skipped}).

Key constitutional enactments (New Zealand has no single codified constitution):

- Constitution Act 1986 — `acts/public/1986/1986-114-constitution-act-1986.md`
- New Zealand Bill of Rights Act 1990 — `acts/public/1990/1990-109-new-zealand-bill-of-rights-act-1990.md`
- Treaty of Waitangi / Te Tiriti o Waitangi (English and Māori texts, from Schedule 1 of the Treaty of
  Waitangi Act 1975) — `constitution/treaty-of-waitangi.md`
- Also: Electoral Act 1993, Senior Courts Act 2016, Legislation Act 2019, Imperial Laws Application
  Act 1988, Treaty of Waitangi Act 1975, etc., under `acts/public/`.

## What is NOT covered (gaps)

- **Acts with no usable archived capture.** Coverage depends on what the Internet Archive crawled;
  in-force Acts whose pages were never archived are missing (e.g. the Parliamentary Privilege Act
  2014). This is not a complete set of the Acts in force. {failed} listed captures could not be
  retrieved.
- **Changes since capture**: amendments or repeals after each file's `archived` date; an Act
  repealed after its last capture is still included here.
- **Repealed Acts**, Bills, Supplementary Order Papers and amendment papers.
- **Secondary legislation** (regulations, orders, rules, bylaws, notices): not included — tens of
  thousands of instruments, many agency-published, and too sparsely archived to be reliable.
- As-enacted (historical) versions; only the latest consolidation is kept.

## Sources

- Official: Parliamentary Counsel Office, [New Zealand Legislation](https://www.legislation.govt.nz)
  (`source` in each file's front matter points to the official latest version).
- Text actually used: [Internet Archive Wayback Machine](https://web.archive.org/) captures of
  `https://www.legislation.govt.nz/act/<subtype>/<year>/<number>/en/latest/` and
  `https://www.legislation.govt.nz/act/<subtype>/<year>/<number>/latest/whole.html`, enumerated
  with the [CDX API](https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server).
- Official API (requires a key from the PCO, `contact@pco.govt.nz`):
  [api.legislation.govt.nz/docs](https://api.legislation.govt.nz/docs/). With a key, a future
  rebuild should switch to the API + official XML.

## Licence / copyright

New Zealand legislation is Crown copyright, licensed for re-use under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
("Source: New Zealand Legislation website, www.legislation.govt.nz"); under section 27 of the
Copyright Act 1994 there is no copyright in Acts of Parliament themselves. This repository
reproduces the text unaltered apart from conversion to Markdown. This is **not** an official
version: under the Legislation Act 2019 only the versions published by the PCO are official.

## Structure

```
acts/public/<year>/<year>-<number>-<slug>.md      Public Acts
acts/local/<year>/…                               Local Acts
acts/private/<year>/…                             Private Acts
acts/provincial/<year>/…                          Provincial Acts
acts/imperial/<year>/…                            Imperial (UK) Acts in force in NZ
constitution/treaty-of-waitangi.md                The Treaty of Waitangi (English and Māori texts)
scripts/                                          fetch + convert code
```

Each file has YAML front matter (`title`, `identifier` — the PCO work id such as
`act_public_1990_109`, `number`, `type`, `subtype`, `date` — date of assent, `last_amended` — the
"version/reprint as at" date, `status`, `source`, `archived_source`, `archived`, `retrieved`,
`administered_by`), then the Act: H1 title, the long title, and the body with parts, subparts,
crossheadings, sections and schedules as nested headings (depth follows the Act's own nesting).
Subsections and paragraphs are paragraphs prefixed with their labels (`(1)`, `(a)`); amendment
history notes are kept as blockquotes; the consolidation notes at the end of each Act are kept.
The table of contents is omitted.

## Regenerating

```sh
pip install -r scripts/requirements.txt
cd scripts
python list_items.py      # enumerate archived Act pages via the Wayback CDX API
python fetch.py           # download captures (cached gzipped in ../../_raw/nz/html/)
python build.py           # convert to Markdown (skips repealed Acts)
python make_readme.py     # refresh this README's counts
```

Raw downloads go to `../_raw/nz/` (override with `LAWCODEX_RAW`) and are not committed. Requests are
rate-limited (≥1 s apart, ≤3 workers) with backoff and a `LawCodex/1.0` User-Agent.
