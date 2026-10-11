"""Convert a legislation.govt.nz classic "whole.html" page into LawCodex Markdown.

The classic PCO HTML rendering nests the document as
  div#legislation > div.act|div.regulation > cover, contents (TOC), front (long title,
  preamble), body (parts > subparts > crossheads/provisions), schedule-group (schedules),
  end (consolidation notes).
Containers whose first child is a heading (part, subpart, prov, schedule, head1...) become
Markdown headings whose level follows the nesting depth (capped at ######, then bold).
"""
import re
from urllib.parse import urljoin

from lxml import html as lhtml

SITE = "https://www.legislation.govt.nz"
_BASE = [SITE + "/"]


def absurl(src):
    return urljoin(_BASE[0], src or "")

SKIP_CLASSES = {"contents", "crest", "cover-properties", "reprint-date", "toc", "reprint-index"}
BLOCK_TAGS = {"div", "p", "table", "ul", "ol", "dl", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
              "pre", "hr", "form", "fieldset"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
LABEL_HEADING_CLASSES = {"label-para", "def-para", "subprov"}


def classes(el):
    return set((el.get("class") or "").split())


def norm_ws(s):
    return re.sub(r"[ \t\r\n ]+", " ", s).strip() if s else ""


_LEAD = re.compile(r"^(\s*)([#>+\-=]|\d+[.)](?=\s)|\*(?=\s))")


def esc(text):
    """Escape Markdown-significant characters in plain text."""
    text = text.replace("\\", "\\\\")
    text = re.sub(r"([*_`\[\]])", r"\\\1", text)
    text = re.sub(r"<(?=[A-Za-z/!])", "&lt;", text)
    return text


def esc_line_start(line):
    m = _LEAD.match(line)
    if m:
        return line[: m.start(2)] + "\\" + line[m.start(2):]
    return line


def inline(el, in_table=False):
    """Render an element's inline content to Markdown (text, emphasis, links reduced to text)."""
    out = []
    if el.text:
        out.append(esc(el.text))
    for ch in el:
        if not isinstance(ch.tag, str):
            if ch.tail:
                out.append(esc(ch.tail))
            continue
        tag = ch.tag.lower()
        cl = classes(ch)
        if tag == "br":
            out.append("<br>" if in_table else "  \n")
        elif tag in ("em", "i") or "italic" in cl:
            inner = inline(ch, in_table).strip()
            out.append(f"*{inner}*" if inner else "")
        elif tag in ("strong", "b") or "def-term" in cl or "bold" in cl:
            inner = inline(ch, in_table).strip()
            out.append(f"**{inner}**" if inner else "")
        elif tag in ("sup", "sub"):
            out.append(f"<{tag}>{inline(ch, in_table)}</{tag}>")
        elif tag == "img":
            src = absurl(ch.get("src"))
            alt = ch.get("alt") or "image"
            out.append(f"![{esc(alt)}]({src})")
        elif tag in ("script", "style"):
            pass
        else:
            out.append(inline(ch, in_table))
        if ch.tail:
            out.append(esc(ch.tail))
    return "".join(out)


def clean_inline(s):
    s = re.sub(r"[ \t\r\n ]+", " ", s.replace("  \n", "\u0000"))
    s = s.replace("\u0000", "  \n")
    s = re.sub(r" *  \n *", "  \n", s)
    return s.strip()


def table_to_md(tbl):
    rows = tbl.xpath(".//tr")
    if not rows:
        return ""
    complex_ = bool(tbl.xpath(".//td[@rowspan>1 or @colspan>1] | .//th[@rowspan>1 or @colspan>1]"))
    complex_ = complex_ or bool(tbl.xpath(".//td//table | .//td//p[2] | .//td//div[@class='para'][2]"))
    grid = []
    for tr in rows:
        cells = tr.xpath("./td|./th")
        grid.append([clean_inline(inline(c, True)).replace("|", "\\|").replace("  \n", "<br>") for c in cells])
    width = max(len(r) for r in grid)
    if width == 0 or all(not "".join(r) for r in grid):
        return ""
    if width == 1:
        # single-column layout tables (signatures, boxed text): render as paragraphs
        return "\n\n".join(r[0].replace("<br>", "  \n") for r in grid if r and r[0])
    if not complex_:
        grid = [r + [""] * (width - len(r)) for r in grid]
        head = grid[0]
        lines = ["| " + " | ".join(head) + " |", "|" + "---|" * width]
        for r in grid[1:]:
            lines.append("| " + " | ".join(r) + " |")
        return "\n".join(lines)
    # complex: keep as minimal HTML
    out = ["<table>"]
    for tr in rows:
        out.append("<tr>")
        for c in tr.xpath("./td|./th"):
            attrs = ""
            for a in ("colspan", "rowspan"):
                if c.get(a) and c.get(a) != "1":
                    attrs += f' {a}="{c.get(a)}"'
            txt = clean_inline(inline(c, True)).replace("  \n", "<br>")
            tag = "th" if c.tag == "th" else "td"
            out.append(f"<{tag}{attrs}>{txt}</{tag}>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


class Renderer:
    def __init__(self):
        self.blocks = []
        self.pending = []  # pending labels to prefix to the next paragraph
        self.quote = 0

    def emit(self, text, raw=False):
        text = text.strip("\n")
        if not text.strip():
            return
        if self.pending:
            lab = " ".join(self.pending)
            self.pending = []
            text = f"{lab} {text}"
        if not raw:
            text = "\n".join(esc_line_start(l) for l in text.split("\n"))
        if self.quote:
            text = "\n".join(("> " + l) if l else ">" for l in text.split("\n"))
        self.blocks.append(text)

    def flush_labels(self):
        if self.pending:
            lab = " ".join(self.pending)
            self.pending = []
            self.blocks.append(("> " if self.quote else "") + lab)

    def heading(self, level, text):
        self.flush_labels()
        text = norm_ws(text)
        if not text:
            return
        if level <= 6:
            self.blocks.append("#" * level + " " + text)
        else:
            self.blocks.append(f"**{text}**")

    def heading_text(self, h):
        label = norm_ws(" ".join(h.xpath(".//span[contains(@class,'label')]//text()")))
        full = clean_inline(inline(h))
        return full if full else label

    def walk(self, el, level):
        for ch in el:
            if not isinstance(ch.tag, str):
                continue
            self.node(ch, level)

    def node(self, el, level):
        tag = el.tag.lower()
        cl = classes(el)
        if cl & SKIP_CLASSES or tag in ("script", "style", "colgroup"):
            return
        if tag == "h1" and "title" in cl and el.xpath("ancestor::div[contains(concat(' ', @class, ' '), ' cover ')]"):
            return
        if tag in HEADINGS:
            if cl & LABEL_HEADING_CLASSES:
                lab = clean_inline(inline(el))
                if lab:
                    self.pending.append(lab)
                return
            self.heading(level, self.heading_text(el))
            return
        if tag == "p" and "subprov" in cl:
            lab = clean_inline(inline(el))
            if lab:
                self.pending.append(f"**{lab}**" if re.match(r"^\\?\(", lab) else lab)
            return
        if tag == "span" and "deletion-status" in cl:
            self.emit(clean_inline(inline(el)))
            return
        if tag == "table":
            md = table_to_md(el)
            if md:
                self.flush_labels()
                self.emit(md, raw=True)
            return
        if tag in ("ul", "ol"):
            if el.xpath("./li/*[self::div or self::p or self::table or self::ul or self::ol]"):
                for li in el.xpath("./li"):
                    self.node_container(li, level)
                return
            self.flush_labels()
            items = []
            for i, li in enumerate(el.xpath("./li"), 1):
                bullet = f"{i}." if tag == "ol" else "-"
                items.append(f"{bullet} {clean_inline(inline(li))}")
            self.emit("\n".join(items), raw=True)
            return
        if tag == "img":
            src = absurl(el.get("src"))
            self.emit(f"![{esc(el.get('alt') or 'image')}]({src})", raw=True)
            return
        if tag == "div" and "history" in cl:
            self.flush_labels()
            self.quote += 1
            self.walk(el, level)
            self.quote -= 1
            return
        if tag == "div":
            self.node_container(el, level)
            return
        if tag in ("p", "span", "a", "em", "strong", "b", "i", "pre", "dd", "dt", "li"):
            if tag == "p" and el.xpath("./table|./div|./p|./ul|./ol"):
                for c in el:
                    if isinstance(c.tag, str):
                        self.node(c, level)
                return
            self.emit(clean_inline(inline(el)))
            return
        # fallback: recurse
        self.walk(el, level)

    def node_container(self, el, level):
        if "cover" in classes(el):
            self.walk(el, level)
            return
        if True:  # noqa
            first = next((c for c in el if isinstance(c.tag, str)), None)
            if (first is not None and first.tag.lower() in HEADINGS
                    and not (classes(first) & LABEL_HEADING_CLASSES)):
                txt = self.heading_text(first)
                if txt:
                    self.heading(level, txt)
                    for c in el:
                        if c is first or not isinstance(c.tag, str):
                            continue
                        self.node(c, level + 1)
                    return
                # empty heading (unlabelled): keep same level, skip heading
                for c in el:
                    if c is first or not isinstance(c.tag, str):
                        continue
                    self.node(c, level)
                return
            # does it contain block children?
            if any(isinstance(c.tag, str) and c.tag.lower() in BLOCK_TAGS | {"span"} and
                   (c.tag.lower() != "span" or "deletion-status" in classes(c)) for c in el):
                if norm_ws(el.text):
                    self.emit(clean_inline(esc(el.text)))
                for c in el:
                    if isinstance(c.tag, str):
                        self.node(c, level)
                    if c.tail and norm_ws(c.tail):
                        self.emit(clean_inline(esc(c.tail)))
                return
            self.emit(clean_inline(inline(el)))
            return


def text_of(root, xp):
    r = root.xpath(xp)
    if not r:
        return ""
    return norm_ws(" ".join(x if isinstance(x, str) else x.text_content() for x in r))


MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                       "august", "september", "october", "november", "december"], 1)}


def parse_date(s):
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)? +([A-Za-z]+),? +(\d{4})", s or "")
    if not m:
        return None
    mo = MONTHS.get(m.group(2).lower())
    if not mo:
        return None
    return f"{int(m.group(3)):04d}-{mo:02d}-{int(m.group(1)):02d}"


def convert(raw_html, base_url=None):
    """Return (meta, markdown_body) for a whole.html page. meta has title, type, number, ..."""
    _BASE[0] = base_url or (SITE + "/")
    doc = lhtml.fromstring(raw_html)
    leg = doc.xpath("//div[@id='legislation']")
    if not leg:
        raise ValueError("no #legislation container")
    leg = leg[0]
    roots = [c for c in leg if isinstance(c.tag, str)]
    meta = {}
    meta["title"] = text_of(leg, "(.//h1[contains(@class,'title')])[1]")
    meta["doc_type"] = text_of(leg, "(.//*[@class='document-type'])[1]")
    meta["number"] = text_of(leg, "(.//*[@class='legislation-number'])[1]")
    meta["assent"] = text_of(leg, "(.//*[@class='assent-date'])[1]")
    meta["made"] = text_of(leg, "(.//*[@class='date-of-making' or @class='made-date'])[1]")
    meta["commencement"] = text_of(leg, "(.//*[@class='commencement'])[1]")
    meta["version"] = text_of(leg, "(.//p[contains(@class,'reprint-date')])[1]")
    meta["admin"] = text_of(leg, "(.//p[@class='admin-office'])[1]")
    alerts = doc.xpath("//li[contains(@id,'documentNavigationHeader_terminated')]")
    meta["terminated"] = norm_ws(alerts[0].text_content()) if alerts else ""
    am = doc.xpath("//li[contains(@id,'documentNavigationHeader_alertMessage')]")
    meta["alert_message"] = norm_ws(am[0].text_content()) if am else ""
    meta["badges"] = [norm_ws(b.text_content()) for b in doc.xpath(
        "(//*[contains(@class,'legislation-overview-component')])[1]//span[contains(@class,'badge-component')]")]
    asat = [norm_ws(x.text_content()) for x in doc.xpath(
        "(//*[contains(@class,'legislation-overview-component')])[1]//span[starts-with(normalize-space(.),'as at')]")]
    meta["banner_asat"] = asat[0] if asat else ""
    head_title = norm_ws(doc.findtext(".//title") or "")
    meta["page_title"] = head_title
    root_el = roots[0] if roots else leg
    meta["root_class"] = root_el.get("class") or ""
    r = Renderer()
    for c in roots:
        r.node(c, 2)
    r.flush_labels()
    body = "\n\n".join(b for b in r.blocks if b.strip())
    body = re.sub(r"\n{3,}", "\n\n", body)
    return meta, body
