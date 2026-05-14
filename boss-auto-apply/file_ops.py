"""Helpers for writing small runtime state files on Windows more safely."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def safe_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    retries: int = 25,
    base_delay: float = 0.04,
) -> None:
    """Write via a unique temp file, retrying around transient replace locks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None

    for attempt in range(retries):
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{int(time.time() * 1000)}.{attempt}.tmp")
        try:
            tmp.write_text(text, encoding=encoding)
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            last_exc = exc
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            time.sleep(min(base_delay * (attempt + 1), 0.5))
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    # Last resort: overwrite in place so monitoring issues do not halt the worker.
    try:
        with path.open("w", encoding=encoding) as handle:
            handle.write(text)
        return
    except Exception:
        if last_exc:
            raise last_exc
        raise


def safe_write_json(
    path: Path,
    payload,
    *,
    ensure_ascii: bool = False,
    indent: int = 2,
    encoding: str = "utf-8",
    retries: int = 25,
    base_delay: float = 0.04,
) -> None:
    text = json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent)
    safe_write_text(
        path,
        text,
        encoding=encoding,
        retries=retries,
        base_delay=base_delay,
    )
