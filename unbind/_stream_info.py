from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(kw_only=True, frozen=True)
class StreamInfo:
    """Metadata about a file stream — compatible with markitdown's StreamInfo."""

    mimetype: Optional[str] = None
    extension: Optional[str] = None
    charset: Optional[str] = None
    filename: Optional[str] = None
    local_path: Optional[str] = None
    url: Optional[str] = None

    def copy_and_update(self, *args, **kwargs):
        new_info = asdict(self)
        for si in args:
            assert isinstance(si, StreamInfo)
            new_info.update({k: v for k, v in asdict(si).items() if v is not None})
        if kwargs:
            new_info.update(kwargs)
        return StreamInfo(**new_info)
