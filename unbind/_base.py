from typing import Any, BinaryIO, Optional
from ._stream_info import StreamInfo


class ConverterResult:
    """The result of converting a document.

    The key difference from markitdown's DocumentConverterResult:
    we carry `images` (dict of filename → bytes) for EPUB packaging.
    """

    def __init__(
        self,
        markdown: str,
        *,
        title: Optional[str] = None,
        images: Optional[dict[str, bytes]] = None,
        metadata: Optional[dict] = None,
    ):
        self.markdown = markdown
        self.title = title
        self.images = images or {}
        self.metadata = metadata or {}

    @property
    def text_content(self) -> str:
        return self.markdown

    def __str__(self) -> str:
        return self.markdown


class Converter:
    """Abstract base for all document converters."""

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        """Quick check: can this converter handle the file?

        IMPORTANT: Must reset file_stream position if read.
        """
        raise NotImplementedError

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> ConverterResult:
        """Convert the document. Only called if accepts() returned True."""
        raise NotImplementedError
