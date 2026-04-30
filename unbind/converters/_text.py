import io
from typing import Any, BinaryIO

from .._base import Converter, ConverterResult
from .._stream_info import StreamInfo

_TEXT_MIME_PREFIXES = ("text/",)
_TEXT_EXTS = {".txt", ".md", ".markdown", ".rst", ".org", ".tex", ".log"}


class PlainTextConverter(Converter):
    """Catch-all for plain text files. Reads as UTF-8."""

    def accepts(self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs) -> bool:
        ext = (stream_info.extension or "").lower()
        mime = (stream_info.mimetype or "").lower()
        if ext in _TEXT_EXTS:
            return True
        if any(mime.startswith(p) for p in _TEXT_MIME_PREFIXES):
            return True
        # Last resort: if nothing is known about the stream, treat as text
        if not ext and not mime:
            return True
        return False

    def convert(self, file_stream: BinaryIO, stream_info: StreamInfo,
                **kwargs) -> ConverterResult:
        data = file_stream.read()
        # Try UTF-8 first, then common fallbacks
        for enc in ("utf-8", "utf-16", "gbk", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = data.decode("utf-8", errors="replace")

        return ConverterResult(markdown=text)
