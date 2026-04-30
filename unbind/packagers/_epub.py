"""EPUB 3.0 packager — Markdown + images → professional EPUB.

Migrated from pdf2epub/modules/mark2epub.py with these changes:
- Non-interactive (metadata passed as param, no input() calls)
- Takes ConverterResult instead of directory
- Preserved: Math→MathML, image optimization, full EPUB 3.0 structure
"""

import io
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from xml.dom import minidom
from xml.sax.saxutils import escape as xml_escape

import latex2mathml.converter
import markdown
from PIL import Image

from .._base import ConverterResult


def package_epub(
    result: ConverterResult,
    output_path: Path,
    *,
    metadata: Optional[dict] = None,
    css: Optional[str] = None,
) -> Path:
    """Package a ConverterResult into an EPUB file.

    Args:
        result: Conversion result (markdown + images)
        output_path: Where to write the .epub file
        metadata: Optional dict with dc:title, dc:creator, etc.
        css: Optional custom CSS string
    """
    meta = _default_metadata(metadata, result.title)
    css_content = css or _default_css()
    images = result.images or {}
    markdown_text = result.markdown

    # Split markdown into chapters by ## headings
    chapters = _split_chapters(markdown_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w") as epub:
        # mimetype must be first and uncompressed (EPUB spec)
        epub.writestr("mimetype", "application/epub+zip")

        # META-INF
        epub.writestr("META-INF/container.xml", _container_xml(), zipfile.ZIP_DEFLATED)

        # CSS
        epub.writestr("OPS/css/style.css", css_content, zipfile.ZIP_DEFLATED)

        # Process images
        processed_images: dict[str, bytes] = {}
        for name, data in images.items():
            try:
                optimized = _optimize_image(data, name)
                processed_images[name] = optimized
            except Exception:
                processed_images[name] = data  # use original

        # Write images
        for name, data in processed_images.items():
            epub.writestr(f"OPS/images/{name}", data, zipfile.ZIP_DEFLATED)

        # Write chapters as XHTML
        chapter_filenames = []
        for i, (title, content) in enumerate(chapters):
            fn = f"s{i:05d}-{_slug(title)}.xhtml"
            chapter_filenames.append(fn)
            xhtml = _chapter_xhtml(content, images.keys())
            epub.writestr(f"OPS/{fn}", xhtml.encode("utf-8"), zipfile.ZIP_DEFLATED)

        # Cover page
        book_title = meta.get("dc:title", "Untitled")
        book_author = meta.get("dc:creator", "")
        epub.writestr("OPS/titlepage.xhtml",
                      _cover_xhtml(book_title, book_author).encode("utf-8"),
                      zipfile.ZIP_DEFLATED)

        # TOC
        epub.writestr("OPS/TOC.xhtml",
                      _toc_xhtml(chapter_filenames, chapters),
                      zipfile.ZIP_DEFLATED)
        epub.writestr("OPS/toc.ncx",
                      _toc_ncx(chapter_filenames, chapters, meta),
                      zipfile.ZIP_DEFLATED)

        # package.opf
        epub.writestr("OPS/package.opf",
                      _package_opf(chapter_filenames, list(processed_images.keys()),
                                   meta),
                      zipfile.ZIP_DEFLATED)

    return output_path


# ── helpers ─────────────────────────────────────────────────────────────

def _default_metadata(user_meta: Optional[dict], title: Optional[str]) -> dict:
    defaults = {
        "dc:title": title or "Untitled Document",
        "dc:creator": "Unknown Author",
        "dc:identifier": f"id-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "dc:language": "en",
        "dc:rights": "All rights reserved",
        "dc:publisher": "unbind",
        "dc:date": datetime.now().strftime("%Y-%m-%d"),
    }
    if user_meta:
        defaults.update(user_meta)
    return defaults


def _default_css() -> str:
    return """body {
  font-family: serif;
  line-height: 1.6;
  margin: 5%;
  max-width: 40em;
}
h1, h2, h3, h4, h5, h6 {
  font-family: sans-serif;
  margin-top: 1.5em;
}
img { max-width: 100%; height: auto; display: block; margin: 1em auto; }
pre, code { font-family: monospace; font-size: 0.9em; }
pre {
  background: #f5f5f5;
  padding: 1em;
  border-radius: 4px;
  overflow-x: auto;
}
blockquote {
  border-left: 3px solid #ccc;
  margin-left: 0;
  padding-left: 1em;
  color: #555;
}
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ddd; padding: 0.5em; text-align: left; }
th { background: #f5f5f5; }
.math-display { display: block; text-align: center; margin: 1em 0; }
.math-inline { display: inline; }
"""


def _split_chapters(text: str) -> list[tuple[str, str]]:
    """Split markdown into chapters at ## headings."""
    # Find all ## headings
    pattern = re.compile(r'^## (.+)$', re.MULTILINE)
    matches = list(pattern.finditer(text))

    if not matches:
        # Single chapter
        title = "Content"
        first = text.find("# ")
        if first >= 0:
            end = text.find("\n", first)
            title = text[first + 2:end].strip()
        return [(title, text)]

    chapters = []
    first = text.find("# ")
    if first >= 0 and first < matches[0].start():
        end = text.find("\n", first)
        title = text[first + 2:end].strip()
        content = text[:matches[0].start()].strip()
        chapters.append((title, content))

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            chapters.append((title, content))

    return chapters or [("Content", text)]


def _slug(text: str) -> str:
    s = re.sub(r'[^\w\s-]', '', text.lower())
    s = re.sub(r'[\s]+', '-', s)
    return s[:50] or "chapter"


def _optimize_image(data: bytes, name: str) -> bytes:
    """Resize and optimize image for EPUB."""
    img = Image.open(io.BytesIO(data))
    if img.mode == "RGBA":
        img = img.convert("RGB")

    max_dim = 1800
    ratio = min(max_dim / max(img.size), 1.0)
    if ratio < 1.0:
        new_size = tuple(int(d * ratio) for d in img.size)
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    ext = Path(name).suffix.lower()
    if ext in (".jpg", ".jpeg"):
        img.save(buf, "JPEG", quality=85, optimize=True)
    elif ext == ".png":
        img.save(buf, "PNG", optimize=True)
    else:
        img.save(buf, "JPEG", quality=85, optimize=True)
    return buf.getvalue()


def _convert_math(html: str) -> str:
    """Replace LaTeX math with MathML, protecting code blocks."""
    placeholders = {}
    counter = [0]

    def mask(m):
        key = f"\x00MASK{counter[0]}\x00"
        counter[0] += 1
        placeholders[key] = m.group(0)
        return key

    masked = re.sub(r'<pre[\s\S]*?</pre>|<code[\s\S]*?</code>', mask, html, flags=re.DOTALL)

    def try_mathml(latex):
        try:
            return latex2mathml.converter.convert(latex)
        except Exception:
            return None

    masked = re.sub(r'<p>\s*\$\$(.*?)\$\$\s*</p>',
                    lambda m: f'<div class="math-display">{try_mathml(m.group(1))}</div>'
                    if try_mathml(m.group(1)) else m.group(0),
                    masked, flags=re.DOTALL)
    masked = re.sub(r'\$\$(.*?)\$\$',
                    lambda m: f'<span class="math-display">{try_mathml(m.group(1))}</span>'
                    if try_mathml(m.group(1)) else m.group(0),
                    masked, flags=re.DOTALL)
    masked = re.sub(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)',
                    lambda m: f'<span class="math-inline">{try_mathml(m.group(1))}</span>'
                    if try_mathml(m.group(1)) else m.group(0),
                    masked, flags=re.DOTALL)

    for key, orig in placeholders.items():
        masked = masked.replace(key, orig)
    return masked


def _chapter_xhtml(md_content: str, image_names) -> str:
    # Fix image paths
    for img_name in image_names:
        escaped = re.escape(img_name)
        md_content = re.sub(
            rf'!\[(.*?)\]\({escaped}\)',
            rf'![\1](images/{img_name})',
            md_content
        )
        md_content = re.sub(
            rf'<img\s+src="{escaped}"',
            f'<img src="images/{img_name}"',
            md_content
        )

    html = markdown.markdown(
        md_content,
        extensions=["codehilite", "tables", "fenced_code", "footnotes"],
        extension_configs={"codehilite": {"guess_lang": False}},
    )
    html = _convert_math(html)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      xmlns:m="http://www.w3.org/1998/Math/MathML"
      lang="en">
<head>
  <meta http-equiv="default-style" content="text/html; charset=utf-8"/>
  <link rel="stylesheet" href="css/style.css" type="text/css" media="all"/>
</head>
<body>
{html}
</body>
</html>"""


def _cover_xhtml(title: str, author: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
<title>Cover</title>
<style>
body {{
    margin: 0; padding: 0; height: 100vh;
    display: flex; justify-content: center; align-items: center;
    font-family: serif;
}}
.cover {{
    padding: 3em; text-align: center; border: 1px solid #ccc;
    max-width: 80%;
}}
h1 {{ font-size: 2em; margin-bottom: 0.5em; line-height: 1.2; color: #333; }}
p {{ font-size: 1.2em; font-style: italic; color: #666; }}
</style>
</head>
<body>
<div class="cover">
  <h1>{xml_escape(title)}</h1>
  <p>{xml_escape(author)}</p>
</div>
</body>
</html>"""


def _toc_xhtml(filenames: list[str], chapters: list[tuple[str, str]]) -> str:
    items = []
    for fn, (title, _) in zip(filenames, chapters):
        items.append(f'<li><a href="{quote(fn)}">{xml_escape(title)}</a></li>')

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops" lang="en">
<head>
  <meta http-equiv="default-style" content="text/html; charset=utf-8"/>
  <title>Contents</title>
  <link rel="stylesheet" href="css/style.css" type="text/css"/>
</head>
<body>
<nav epub:type="toc" role="doc-toc" id="toc">
<h2>Contents</h2>
<ol epub:type="list">
{''.join(items)}
</ol>
</nav>
</body>
</html>"""


def _toc_ncx(filenames: list[str], chapters: list[tuple[str, str]],
             meta: dict) -> str:
    uid = xml_escape(meta.get("dc:identifier", ""))
    title = xml_escape(meta.get("dc:title", ""))

    points = []
    for i, (fn, (ch_title, _)) in enumerate(zip(filenames, chapters)):
        src = quote(fn)
        points.append(
            f'<navPoint id="navpoint-{i}" playOrder="{i + 1}">\n'
            f'  <navLabel><text>{xml_escape(ch_title)}</text></navLabel>\n'
            f'  <content src="{src}"/>\n'
            f'</navPoint>'
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" xml:lang="en" version="2005-1">
<head>
  <meta name="dtb:uid" content="{uid}"/>
  <meta name="dtb:depth" content="1"/>
  <meta name="dtb:totalPageCount" content="0"/>
  <meta name="dtb:maxPageNumber" content="0"/>
</head>
<docTitle><text>{title}</text></docTitle>
<navMap>
{''.join(points)}
</navMap>
</ncx>"""


def _container_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" ?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles>
<rootfile full-path="OPS/package.opf" media-type="application/oebps-package+xml"/>
</rootfiles>
</container>"""


def _package_opf(md_fns: list[str], img_fns: list[str], meta: dict) -> str:
    doc = minidom.Document()
    package = doc.createElement("package")
    package.setAttribute("xmlns", "http://www.idpf.org/2007/opf")
    package.setAttribute("version", "3.0")
    package.setAttribute("xml:lang", "en")
    package.setAttribute("unique-identifier", "pub-id")

    # Metadata
    metadata = doc.createElement("metadata")
    metadata.setAttribute("xmlns:dc", "http://purl.org/dc/elements/1.1/")

    for key, val in meta.items():
        el = doc.createElement(key)
        if key in ("dc:title", "dc:creator", "dc:identifier"):
            id_map = {"dc:title": "title", "dc:creator": "creator",
                      "dc:identifier": "pub-id"}
            el.setAttribute("id", id_map.get(key, ""))
        el.appendChild(doc.createTextNode(str(val)))
        metadata.appendChild(el)

    modified = doc.createElement("meta")
    modified.setAttribute("property", "dcterms:modified")
    modified.appendChild(doc.createTextNode(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    metadata.appendChild(modified)

    # Manifest
    manifest = doc.createElement("manifest")

    _add_item(doc, manifest, "toc", "TOC.xhtml", "application/xhtml+xml",
              properties="nav")
    _add_item(doc, manifest, "ncx", "toc.ncx", "application/x-dtbncx+xml")
    _add_item(doc, manifest, "titlepage", "titlepage.xhtml", "application/xhtml+xml")

    for i, fn in enumerate(md_fns):
        _add_item(doc, manifest, f"s{i:05d}", fn, "application/xhtml+xml")

    for i, fn in enumerate(img_fns):
        ext = Path(fn).suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".gif": "image/gif", ".svg": "image/svg+xml"}
        mtype = mime_map.get(ext, "image/jpeg")
        props = "cover-image" if fn == meta.get("cover_image") else None
        _add_item(doc, manifest, f"image-{i:05d}", f"images/{fn}", mtype,
                  properties=props)

    _add_item(doc, manifest, "css-00000", "css/style.css", "text/css")

    # Spine
    spine = doc.createElement("spine")
    spine.setAttribute("toc", "ncx")
    _add_itemref(doc, spine, "titlepage", linear="yes")
    for i in range(len(md_fns)):
        _add_itemref(doc, spine, f"s{i:05d}")

    # Guide (for compatibility)
    guide = doc.createElement("guide")
    ref = doc.createElement("reference")
    ref.setAttribute("type", "cover")
    ref.setAttribute("title", "Cover image")
    ref.setAttribute("href", "titlepage.xhtml")
    guide.appendChild(ref)

    package.appendChild(metadata)
    package.appendChild(manifest)
    package.appendChild(spine)
    package.appendChild(guide)
    doc.appendChild(package)

    return doc.toprettyxml()


def _add_item(doc, parent, id_, href, media_type, *, properties=None):
    el = doc.createElement("item")
    el.setAttribute("id", id_)
    el.setAttribute("href", href)
    el.setAttribute("media-type", media_type)
    if properties:
        el.setAttribute("properties", properties)
    parent.appendChild(el)


def _add_itemref(doc, parent, idref, linear="yes"):
    el = doc.createElement("itemref")
    el.setAttribute("idref", idref)
    el.setAttribute("linear", linear)
    parent.appendChild(el)
