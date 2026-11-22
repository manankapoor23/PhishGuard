"""Build the course report PDF from course_report.md, in the course's required format.

Run (from the repository root; needs Google Chrome):
    uv run --no-project --with mistune --with pypdf python docs/report/make_report.py

Format (from the course's "Machine Learning Project Report Format"): A4, Times New Roman 12 pt,
1.5 line spacing, justified; chapter headings 16 pt bold, section headings 14 pt bold; cover page,
abstract, table of contents, lists of figures and tables; numbered figures and tables with captions.

Two passes: the first PDF locates each heading's page (via invisible markers), the second
writes those page numbers into the table of contents.
"""

import html
import re
import subprocess
import tempfile
from pathlib import Path

import mistune
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "course_report.md"
OUTPUT = HERE / "PhishGuard_Course_Report.pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

COVER = {
    "title": "PhishGuard: What Does a Phishing URL Detector Really Learn?",
    "subtitle": "Machine Learning Project Report",
    "students": [("Manan Kapoor", "1024030467"), ("Shaurya Sangwan", "1024030462"), ("Abhishek Batra", "1024030463")],
    "supervisor": "Mahak Gambhir",
    "department": "",
    "institute": "TIET",
    "date": "November 2026",
}

CSS = """
@page { size: A4; margin: 22mm 22mm 20mm; @bottom-center { content: counter(page); font-family: 'Times New Roman', serif; font-size: 11pt; } }
@page cover { @bottom-center { content: none; } }
body { font-family: 'Times New Roman', Times, serif; font-size: 12pt; line-height: 1.5; color: #000; text-align: justify; }
h1 { font-size: 16pt; font-weight: bold; margin: 0 0 14pt; break-before: page; text-align: left; }
h2 { font-size: 14pt; font-weight: bold; margin: 16pt 0 6pt; break-after: avoid; text-align: left; }
p { margin: 0 0 6pt; }
ul, ol { margin: 0 0 8pt; padding-left: 22pt; }
li { margin: 0 0 3pt; }
code { font-family: 'Courier New', monospace; font-size: 10.5pt; }
table { border-collapse: collapse; width: 100%; font-size: 11pt; line-height: 1.3; text-align: left; margin: 2pt 0 12pt; }
th, td { border: 1px solid #888; padding: 4pt 6pt; vertical-align: top; }
th { background: #E8ECF1; font-weight: bold; }
.tbl { break-inside: avoid; }
.caption { font-size: 11pt; font-weight: bold; text-align: center; margin: 10pt 0 4pt; }
figure { margin: 8pt 0 10pt; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; max-height: 70mm; }
figure.wide img { max-height: 90mm; }
figcaption { font-size: 11pt; font-weight: bold; margin-top: 4pt; }
.marker { font-size: 1px; color: #fff; }
.refs p { font-size: 11pt; line-height: 1.35; text-align: left; margin-bottom: 5pt; }
.cover { page: cover; text-align: center; padding-top: 30mm; }
.cover .t { font-size: 22pt; font-weight: bold; line-height: 1.3; margin-bottom: 10pt; }
.cover .s { font-size: 16pt; margin-bottom: 40mm; }
.cover table { width: 70%; margin: 0 auto 18mm; font-size: 12pt; }
.cover td, .cover th { border: none; text-align: left; background: none; }
.cover .meta { font-size: 13pt; line-height: 1.7; }
.toc { list-style: none; padding: 0; margin: 0; text-align: left; }
.toc { font-size: 11pt; line-height: 1.3; }
.toc li { display: flex; margin: 0 0 1pt; }
.toc li .dots { flex: 1; border-bottom: 1px dotted #666; margin: 0 4pt 5pt; }
.toc li.l2 { padding-left: 18pt; }
.toc li.l1 { font-weight: bold; margin-top: 4pt; }
h1.nobreak, h1.flow { break-before: auto; margin-top: 24pt; break-after: avoid; }
"""


def build_body(md: str):
    """Markdown → HTML with numbered chapters, figures and tables; returns html, headings, figures, tables."""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    body = mistune.create_markdown(plugins=["table"], escape=False)(md)
    headings, figures, tables = [], [], []
    state = {"chapter": None, "fig": 0, "tab": 0, "n": 0}

    def heading(match):
        level, text = int(match.group(1)), match.group(2)
        state["n"] += 1
        key = f"H{state['n']:03d}"
        plain = html.unescape(re.sub(r"<[^>]+>", "", text))
        chapter = re.match(r"Chapter (\d+):", plain)
        if level == 1:
            state["chapter"] = chapter.group(1) if chapter else None
            state["fig"] = state["tab"] = 0
        headings.append((level, plain, key))
        # Chapters 2–7 continue on the same page (the format sets no page breaks); Chapter 1, References start one.
        cls = ' class="flow"' if level == 1 and chapter and chapter.group(1) != "1" else ""
        return f'<h{level}{cls}>{text}<span class="marker">@@{key}@@</span></h{level}>'

    body = re.sub(r"<h([12])>(.*?)</h\1>", heading, body)

    # Number figures and tables per chapter, in document order.
    def number(kind):
        state[kind] += 1
        return f"{state['chapter']}.{state[kind]}" if state["chapter"] else str(state[kind])

    out, pos = [], 0
    pattern = re.compile(r'(<h1[^>]*>.*?</h1>)|<p><img src="([^"]+)" alt="([^"]*)" ?/?></p>|<p>Table: (.*?)</p>\s*(<table>.*?</table>)', re.S)
    for m in pattern.finditer(body):
        out.append(body[pos:m.start()])
        if m.group(1):
            level_text = re.sub(r"<[^>]+>", "", m.group(1))
            chapter = re.match(r"Chapter (\d+):", html.unescape(level_text))
            state["chapter"] = chapter.group(1) if chapter else None
            state["fig"] = state["tab"] = 0
            out.append(m.group(1))
        elif m.group(2):
            n = number("fig")
            caption = m.group(3)
            figures.append((n, html.unescape(caption), f"F{n}"))
            wide = ' class="wide"' if "workflow" in m.group(2) or "website" in m.group(2) else ""
            src = (HERE / m.group(2)).as_uri()
            out.append(f'<figure{wide}><img src="{src}" alt="{caption}"><figcaption>Figure {n}: {caption}'
                       f'<span class="marker">@@F{n}@@</span></figcaption></figure>')
        else:
            n = number("tab")
            caption = m.group(4)
            tables.append((n, html.unescape(re.sub(r"<[^>]+>", "", caption)), f"T{n}"))
            out.append(f'<div class="tbl"><p class="caption">Table {n}: {caption}<span class="marker">@@T{n}@@</span></p>{m.group(5)}</div>')
        pos = m.end()
    out.append(body[pos:])
    return "".join(out), headings, figures, tables


def cover_html():
    c = COVER
    rows = "".join(f"<tr><td>{name}</td><td>{roll}</td></tr>" for name, roll in c["students"])
    return f"""<section class="cover">
<p class="t">{c['title']}</p><p class="s">{c['subtitle']}</p>
<p style="font-weight:bold;margin-bottom:6pt">Submitted by</p>
<table><tr><th>Name</th><th>Roll number</th></tr>{rows}</table>
<p class="meta">Under the supervision of <b>{c['supervisor']}</b><br>{c['department'] + '<br>' if c['department'] else ''}{c['institute']}<br>{c['date']}</p>
</section>"""


def toc_html(headings, figures, tables, pages):
    def line(text, key, cls=""):
        return f'<li class="{cls}"><span>{html.escape(text)}</span><span class="dots"></span><span>{pages.get(key, "")}</span></li>'
    toc = [line(t, k, "l1" if lvl == 1 else "l2") for lvl, t, k in headings]
    lof = [line(f"Figure {n}: {c}", k) for n, c, k in figures]
    lot = [line(f"Table {n}: {c}", k) for n, c, k in tables]
    return (f'<h1>Table of Contents</h1><ul class="toc">{"".join(toc)}</ul>'
            f'<h1>List of Figures</h1><ul class="toc">{"".join(lof)}</ul>'
            f'<h2>List of Tables</h2><ul class="toc">{"".join(lot)}</ul>')


def render(page_html: str, pdf: Path):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page_html)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=10000",
                    f"--print-to-pdf={pdf}", Path(f.name).as_uri()], check=True, capture_output=True)


def main():
    body, headings, figures, tables = build_body(SOURCE.read_text())
    # The abstract comes before the table of contents; everything else after it.
    abstract_end = body.index("<h1>Chapter 1:")
    abstract, rest = body[:abstract_end], body[abstract_end:].replace("<h1>Appendix", '</div><h1 class="nobreak">Appendix')
    rest = re.sub(r"(<h1>References.*?</h1>)", r'\1<div class="refs">', rest, count=1, flags=re.S)
    toc_headings = [h for h in headings if not h[1].startswith("Abstract")]

    def page(pages):
        return (f'<!doctype html><html><head><meta charset="utf-8"><title>PhishGuard report</title><style>{CSS}</style></head>'
                f"<body>{cover_html()}{abstract}{toc_html(toc_headings, figures, tables, pages)}{rest}</body></html>")

    first = OUTPUT.with_suffix(".pass1.pdf")
    render(page({}), first)
    pages = {}
    for number, p in enumerate(PdfReader(first).pages, start=1):
        for key in re.findall(r"@@([HFT][\d.]+)@@", p.extract_text() or ""):
            pages.setdefault(key, number)
    first.unlink()
    render(page(pages), OUTPUT)
    count = len(PdfReader(OUTPUT).pages)
    words = len(re.sub(r"<[^>]+>", " ", abstract.split("</h1>", 1)[1]).split())
    print(f"{OUTPUT.name}: {count} pages, {len(figures)} figures, {len(tables)} tables, abstract {words} words; "
          f"{len(pages)} of {len(toc_headings) + len(figures) + len(tables)} entries located")


if __name__ == "__main__":
    main()
