import io
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, List, Optional, Union
from urllib.parse import urlparse

import charset_normalizer
import requests

from ._base import Converter, ConverterResult
from ._stream_info import StreamInfo
from ._exceptions import (
    FileConversionException,
    FailedConversionAttempt,
    UnsupportedFormatException,
)

PRIORITY_SPECIFIC = 0.0   # e.g., .pdf, .docx
PRIORITY_GENERIC = 10.0   # catch-all like text/*


@dataclass(kw_only=True, frozen=True)
class _Registration:
    converter: Converter
    priority: float


class Unbind:
    """Universal document unbinder.

    Any format in → Markdown (for AI) or EPUB (for humans) out.
    """

    def __init__(
        self,
        *,
        requests_session: Optional[requests.Session] = None,
    ):
        self._session = requests_session or requests.Session()
        self._session.headers.update({
            "Accept": "text/markdown, text/html;q=0.9, text/plain;q=0.8, */*;q=0.1"
        })
        self._converters: List[_Registration] = []

        # Lazy imports to keep core deps light
        self._magika = None

    # ── converter registry ──────────────────────────────────────────

    def register(self, converter: Converter, *, priority: float = PRIORITY_SPECIFIC):
        """Register a converter. Lower priority = tried first."""
        self._converters.insert(0, _Registration(converter=converter, priority=priority))

    def enable_builtins(self):
        """Register all built-in converters."""
        from .converters._pdf import PdfConverter
        from .converters._delegating import DelegatingConverter
        from .converters._text import PlainTextConverter

        self.register(PlainTextConverter(), priority=PRIORITY_GENERIC)
        self.register(DelegatingConverter(), priority=PRIORITY_SPECIFIC + 1)
        self.register(PdfConverter(), priority=PRIORITY_SPECIFIC)

    # ── public API ──────────────────────────────────────────────────

    def convert(self, source: Union[str, Path, BinaryIO, requests.Response],
                **kwargs) -> ConverterResult:
        """Convert any document source to a ConverterResult (markdown + images).

        source: file path, URL, Path, BinaryIO stream, or requests.Response.
        """
        if isinstance(source, (str, Path)):
            s = str(source)
            if s.startswith(("http:", "https:", "file:", "data:")):
                return self._convert_uri(s, **kwargs)
            return self._convert_local(Path(s), **kwargs)
        elif isinstance(source, requests.Response):
            return self._convert_response(source, **kwargs)
        elif hasattr(source, "read") and callable(source.read):
            return self._convert_stream(source, **kwargs)
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

    def extract(self, source: Union[str, Path, BinaryIO],
                output_dir: Optional[Union[str, Path]] = None,
                **kwargs) -> ConverterResult:
        """Convert to Markdown and save to output_dir (or return result only).

        If output_dir is given, writes {stem}.md and images/ into that directory.
        """
        result = self.convert(source, **kwargs)

        if output_dir is not None:
            od = Path(output_dir)
            od.mkdir(parents=True, exist_ok=True)

            # Determine stem from source if possible
            stem = "output"
            if isinstance(source, (str, Path)) and not str(source).startswith("http"):
                stem = Path(source).stem
            elif result.title:
                stem = re.sub(r'[^\w\-]', '_', result.title)[:60]

            md_path = od / f"{stem}.md"
            md_path.write_text(result.markdown, encoding="utf-8")

            if result.images:
                img_dir = od / "images"
                img_dir.mkdir(exist_ok=True)
                for name, data in result.images.items():
                    (img_dir / name).write_bytes(data)

        return result

    def bind(self, source: Union[str, Path, BinaryIO],
             output_path: Optional[Union[str, Path]] = None,
             *,
             metadata: Optional[dict] = None,
             **kwargs) -> Path:
        """Convert to EPUB. Returns path to the generated .epub file."""
        result = self.convert(source, **kwargs)

        if output_path is None:
            stem = "output"
            if isinstance(source, (str, Path)):
                stem = Path(source).stem
            output_path = Path.cwd() / f"{stem}.epub"
        else:
            output_path = Path(output_path)

        from .packagers._epub import package_epub
        return package_epub(result, output_path, metadata=metadata)

    # ── internal routing ────────────────────────────────────────────

    def _convert_local(self, path: Path, **kwargs) -> ConverterResult:
        base = StreamInfo(
            local_path=str(path),
            extension=os.path.splitext(path.name)[1],
            filename=path.name,
        )
        with open(path, "rb") as fh:
            guesses = self._guess(fh, base)
            return self._do_convert(fh, guesses, **kwargs)

    def _convert_stream(self, stream: BinaryIO,
                        stream_info: Optional[StreamInfo] = None,
                        **kwargs) -> ConverterResult:
        if not stream.seekable():
            buf = io.BytesIO(stream.read())
            buf.seek(0)
            stream = buf
        guesses = self._guess(stream, stream_info or StreamInfo())
        return self._do_convert(stream, guesses, **kwargs)

    def _convert_uri(self, uri: str, **kwargs) -> ConverterResult:
        if uri.startswith("file:"):
            path = uri[5:].lstrip("/")
            return self._convert_local(Path(path), **kwargs)
        if uri.startswith("data:"):
            # minimal data URI support
            header, b64 = uri[5:].split(";base64,", 1)
            import base64
            data = base64.b64decode(b64)
            info = StreamInfo(mimetype=header or None)
            return self._convert_stream(io.BytesIO(data), stream_info=info, **kwargs)
        # http/https
        resp = self._session.get(uri, stream=True)
        resp.raise_for_status()
        return self._convert_response(resp, **kwargs)

    def _convert_response(self, resp: requests.Response, **kwargs) -> ConverterResult:
        info = StreamInfo(url=resp.url)
        if "content-type" in resp.headers:
            parts = resp.headers["content-type"].split(";")
            info = info.copy_and_update(mimetype=parts[0].strip())
        if "content-disposition" in resp.headers:
            m = re.search(r'filename=([^;]+)', resp.headers["content-disposition"])
            if m:
                fname = m.group(1).strip('"\'')
                info = info.copy_and_update(filename=fname,
                                            extension=os.path.splitext(fname)[1])
        buf = io.BytesIO()
        for chunk in resp.iter_content(8192):
            buf.write(chunk)
        buf.seek(0)
        guesses = self._guess(buf, info)
        return self._do_convert(buf, guesses, **kwargs)

    def _do_convert(self, file_stream: BinaryIO,
                    guesses: List[StreamInfo], **kwargs) -> ConverterResult:
        failed: List[FailedConversionAttempt] = []
        sorted_regs = sorted(self._converters, key=lambda r: r.priority)
        cur_pos = file_stream.tell()

        for info in guesses + [StreamInfo()]:
            for reg in sorted_regs:
                assert file_stream.tell() == cur_pos
                try:
                    ok = reg.converter.accepts(file_stream, info, **kwargs)
                except NotImplementedError:
                    ok = False
                assert file_stream.tell() == cur_pos

                if not ok:
                    continue
                res = None
                try:
                    res = reg.converter.convert(file_stream, info, **kwargs)
                except Exception:
                    failed.append(FailedConversionAttempt(
                        converter=reg.converter, exc_info=sys.exc_info()
                    ))
                finally:
                    file_stream.seek(cur_pos)

                if res is not None:
                    # Normalize newlines
                    res.markdown = "\n".join(
                        line.rstrip() for line in re.split(r"\r?\n", res.markdown)
                    )
                    res.markdown = re.sub(r"\n{3,}", "\n\n", res.markdown)
                    return res

        if failed:
            raise FileConversionException(attempts=failed)
        raise UnsupportedFormatException(
            "No converter could handle this document."
        )

    def _guess(self, file_stream: BinaryIO,
               base: StreamInfo) -> List[StreamInfo]:
        """Build a list of StreamInfo guesses, from most to least likely."""
        guesses: List[StreamInfo] = []

        enhanced = base.copy_and_update()
        if base.mimetype is None and base.extension:
            m, _ = mimetypes.guess_type("x" + base.extension, strict=False)
            if m:
                enhanced = enhanced.copy_and_update(mimetype=m)
        if base.mimetype and base.extension is None:
            exts = mimetypes.guess_all_extensions(base.mimetype, strict=False)
            if exts:
                enhanced = enhanced.copy_and_update(extension=exts[0])

        # Try magika for content-based detection
        cur_pos = file_stream.tell()
        try:
            if self._magika is None:
                try:
                    import magika
                    self._magika = magika.Magika()
                except Exception:
                    guesses.append(enhanced)
                    return guesses

            result = self._magika.identify_stream(file_stream)
            if result.status == "ok" and result.prediction.output.label != "unknown":
                guessed_ext = None
                if result.prediction.output.extensions:
                    guessed_ext = "." + result.prediction.output.extensions[0]

                compatible = True
                if base.mimetype and base.mimetype != result.prediction.output.mime_type:
                    compatible = False
                if base.extension and base.extension.lstrip(".") not in result.prediction.output.extensions:
                    compatible = False

                if compatible:
                    guesses.append(StreamInfo(
                        mimetype=base.mimetype or result.prediction.output.mime_type,
                        extension=base.extension or guessed_ext,
                        filename=base.filename,
                        local_path=base.local_path,
                        url=base.url,
                    ))
                else:
                    guesses.append(enhanced)
                    guesses.append(StreamInfo(
                        mimetype=result.prediction.output.mime_type,
                        extension=guessed_ext,
                        filename=base.filename,
                        local_path=base.local_path,
                        url=base.url,
                    ))
            else:
                guesses.append(enhanced)
        except Exception:
            guesses.append(enhanced)
        finally:
            file_stream.seek(cur_pos)

        return guesses or [enhanced]
