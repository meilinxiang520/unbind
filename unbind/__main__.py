"""unbind — universal document unbinder.

Usage:
    unbind extract <source>          Convert to Markdown
    unbind bind <source>             Convert to EPUB

    <source> can be a file path, URL, or '-' for stdin.

Examples:
    unbind extract report.pdf                     # → report.md + images/
    unbind extract report.pdf -o ./out            # → ./out/report.md
    unbind bind report.pdf                        # → report.epub
    unbind bind report.pdf -o book.epub           # → book.epub
    unbind bind slides.pptx --title "My Deck"     # → slides.epub
    unbind bind https://example.com/doc.html      # → doc.epub
    cat draft.txt | unbind bind -                 # stdin → output.epub
"""

import argparse
import io
import sys
from pathlib import Path

from ._engine import Unbind


def main():
    parser = argparse.ArgumentParser(
        prog="unbind",
        description="Universal document unbinder: any format → Markdown or EPUB",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # extract
    ex = sub.add_parser("extract", help="Convert to Markdown")
    ex.add_argument("source", help="File path, URL, or '-' for stdin")
    ex.add_argument("-o", "--output-dir", help="Output directory")
    ex.add_argument("--max-pages", type=int, help="Max pages (PDF only)")
    ex.add_argument("--start-page", type=int, default=0, help="Start page (PDF only)")

    # bind
    bd = sub.add_parser("bind", help="Convert to EPUB")
    bd.add_argument("source", help="File path, URL, or '-' for stdin")
    bd.add_argument("-o", "--output", help="Output .epub path")
    bd.add_argument("--title", help="Book title")
    bd.add_argument("--author", help="Book author")
    bd.add_argument("--language", default="en", help="Language code")
    bd.add_argument("--max-pages", type=int, help="Max pages (PDF only)")
    bd.add_argument("--start-page", type=int, default=0, help="Start page (PDF only)")

    args = parser.parse_args()
    unbind = Unbind()
    unbind.enable_builtins()

    source = _resolve_source(args.source)

    conv_kwargs = {}
    if hasattr(args, "max_pages") and args.max_pages:
        conv_kwargs["max_pages"] = args.max_pages
    if hasattr(args, "start_page"):
        conv_kwargs["start_page"] = args.start_page

    try:
        if args.command == "extract":
            output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
            result = unbind.extract(source, output_dir=output_dir, **conv_kwargs)
            print(f"✓ Markdown extracted ({len(result.markdown)} chars)")
            if result.images:
                print(f"✓ {len(result.images)} images saved")

        elif args.command == "bind":
            output = Path(args.output) if args.output else None
            meta = {}
            if hasattr(args, "title") and args.title:
                meta["dc:title"] = args.title
            if hasattr(args, "author") and args.author:
                meta["dc:creator"] = args.author
            if hasattr(args, "language"):
                meta["dc:language"] = args.language

            epub_path = unbind.bind(source, output_path=output, metadata=meta,
                                    **conv_kwargs)
            print(f"✓ EPUB created: {epub_path}")
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def _resolve_source(source: str):
    if source == "-":
        return io.BytesIO(sys.stdin.buffer.read())
    return source


if __name__ == "__main__":
    main()
