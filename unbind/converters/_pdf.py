import io
import json
import sys
from pathlib import Path
from typing import Any, BinaryIO

from PIL import Image

from .._base import Converter, ConverterResult
from .._stream_info import StreamInfo
from .._exceptions import MissingDependencyException

ACCEPTED_MIMES = ["application/pdf", "application/x-pdf"]
ACCEPTED_EXTS = [".pdf"]


class PdfConverter(Converter):
    """High-quality PDF conversion using marker-pdf (AI model).

    Compared to markitdown's PdfConverter (pdfminer/pdfplumber):
    - Superior layout preservation (headings, columns, lists)
    - Math formula detection and LaTeX output
    - Full image extraction with filenames
    - Table structure recognition
    """

    def accepts(self, file_stream: BinaryIO, stream_info: StreamInfo, **kwargs) -> bool:
        ext = (stream_info.extension or "").lower()
        mime = (stream_info.mimetype or "").lower()
        if ext in ACCEPTED_EXTS:
            return True
        return any(mime.startswith(p) for p in ACCEPTED_MIMES)

    def convert(self, file_stream: BinaryIO, stream_info: StreamInfo,
                **kwargs) -> ConverterResult:
        try:
            from marker.models import create_model_dict
            from marker.converters.pdf import PdfConverter as MarkerPdfConverter
        except ImportError:
            raise MissingDependencyException(
                "marker-pdf is required for PDF conversion. "
                "Install with: pip install marker-pdf"
            )

        pdf_bytes = file_stream.read()

        # Build page range config if requested
        config = {}
        max_pages = kwargs.get("max_pages")
        start_page = kwargs.get("start_page", 0)
        if max_pages is not None:
            config["page_range"] = list(range(start_page, start_page + max_pages))

        models = create_model_dict()
        converter = MarkerPdfConverter(config=config, artifact_dict=models)

        # marker-pdf expects a file path, so write to temp
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(pdf_bytes)
            tmp_path = tf.name

        try:
            rendered = converter(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        # Extract images as bytes
        images: dict[str, bytes] = {}
        if rendered.images:
            for filename, img_data in rendered.images.items():
                try:
                    if isinstance(img_data, Image.Image):
                        buf = io.BytesIO()
                        img_data.save(buf, format="PNG")
                        images[filename] = buf.getvalue()
                        img_data.close()
                    elif isinstance(img_data, bytes):
                        images[filename] = img_data
                    elif isinstance(img_data, str) and Path(img_data).exists():
                        images[filename] = Path(img_data).read_bytes()
                except Exception:
                    continue

        return ConverterResult(
            markdown=rendered.markdown,
            title=rendered.metadata.get("title") if rendered.metadata else None,
            images=images,
            metadata=rendered.metadata or {},
        )
