import io
from typing import Any, BinaryIO

from markitdown import MarkItDown, StreamInfo as MStreamInfo

from .._base import Converter, ConverterResult
from .._stream_info import StreamInfo

# Formats handled by markitdown that we don't have a better converter for:
# DOCX, PPTX, XLSX, XLS, EPUB, HTML, CSV, RSS, Jupyter, images, audio
# (PDF is handled by our own PdfConverter with marker-pdf)
_DELEGATED_MIMES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/epub+zip",
    "text/html",
    "text/csv",
    "text/x-rss",
    "application/rss+xml",
    "application/json",
    "application/x-ipynb+json",
}

_DELEGATED_EXTS = {
    ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".epub", ".html", ".htm", ".csv", ".json", ".ipynb",
    ".xml", ".rss", ".msg",
}

_DELEGATED_MIME_PREFIXES = (
    "image/", "audio/",
)


class DelegatingConverter(Converter):
    """Proxies markitdown's built-in converters for non-PDF formats.

    This avoids reinventing the wheel — markitdown already has good converters
    for DOCX, PPTX, XLSX, HTML, EPUB, CSV, etc. We just wrap them.
    """

    def __init__(self):
        self._md = MarkItDown()

    def accepts(self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs) -> bool:
        ext = (stream_info.extension or "").lower()
        mime = (stream_info.mimetype or "").lower()

        # Never accept PDF — our PdfConverter handles that
        if ext == ".pdf" or mime.startswith("application/pdf"):
            return False

        if ext in _DELEGATED_EXTS:
            return True
        if mime in _DELEGATED_MIMES:
            return True
        if any(mime.startswith(p) for p in _DELEGATED_MIME_PREFIXES):
            return True
        # For URLs without clear extension, let markitdown try
        if stream_info.url and stream_info.url.startswith("http"):
            return True
        return False

    def convert(self, file_stream: BinaryIO, stream_info: StreamInfo,
                **kwargs) -> ConverterResult:
        # Build a markitdown-compatible StreamInfo
        msi = MStreamInfo(
            mimetype=stream_info.mimetype,
            extension=stream_info.extension,
            charset=stream_info.charset,
            filename=stream_info.filename,
            local_path=stream_info.local_path,
            url=stream_info.url,
        )

        # If we have a URL, use convert_url; otherwise convert_stream
        if stream_info.url and stream_info.url.startswith("http"):
            result = self._md.convert_url(stream_info.url, stream_info=msi)
        else:
            result = self._md.convert_stream(file_stream, stream_info=msi)

        return ConverterResult(
            markdown=result.markdown,
            title=result.title,
        )
