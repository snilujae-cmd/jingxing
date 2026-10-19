"""Share the most recently published simulation on one Streamlit server.

The complete four-CSV ZIP is replaced atomically so readers never combine
different runs. For multiple server instances, point all instances at a
shared mounted path or replace this backend with a database/object store.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED
from zlib import error as ZlibError

import pandas as pd

from admin_auth import assert_admin
from comparison_data import (COMPARISON_NAME, MAX_COMPARISON_BYTES,
                             ComparisonDataError, build_comparison, decode_comparison,
                             encode_comparison, validate_selected_run)
from core.exporter import zip_content
from user_data_adapter import RunData, load_run_zip


DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "shared" / "current_run.zip"
ENV_PATH = "JINGXING_SHARED_RUN_PATH"


@dataclass
class SharedBundle:
    """A single archive snapshot; optional comparison cannot mix with another run."""
    run: RunData | None
    comparison: dict | None = None
    comparison_error: str | None = None


def shared_run_path() -> Path:
    configured = os.environ.get(ENV_PATH)
    return Path(configured).expanduser() if configured else DEFAULT_PATH


def publish_result(result: dict, path: str | Path | None = None,
                   comparison_results: list[dict] | None = None) -> Path:
    """Publish unchanged CSVs plus optional fair-comparison metadata atomically.

    Publishing a single result replaces the whole archive, intentionally removing
    any older comparison. Readers therefore never attach stale strategy data.
    """
    assert_admin()
    comparison = None
    if comparison_results is not None:
        comparison = encode_comparison(build_comparison(comparison_results, result))
    contents = zip_content(result)
    if comparison is not None:
        buffer = BytesIO(contents)
        with ZipFile(buffer, "a", ZIP_DEFLATED) as archive:
            archive.writestr(COMPARISON_NAME, comparison)
        contents = buffer.getvalue()
    target = Path(path) if path is not None else shared_run_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".current_run_", suffix=".zip.tmp",
            dir=target.parent, delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def load_shared_bundle(stations: pd.DataFrame, path: str | Path | None = None) -> SharedBundle:
    """Read once; comparison errors degrade gracefully to a valid single run."""
    target = Path(path) if path is not None else shared_run_path()
    if not target.is_file():
        return SharedBundle(None)
    contents = target.read_bytes()
    run = load_run_zip(contents, stations)
    run.source_label = "同一站点共享的Admin最新仿真"
    comparison = None
    try:
        with ZipFile(BytesIO(contents)) as archive:
            entries = [info for info in archive.infolist() if info.filename == COMPARISON_NAME]
            if not entries:
                return SharedBundle(run)
            if len(entries) != 1 or entries[0].is_dir():
                raise ComparisonDataError("共享包中的三策略比较文件重复或无效")
            if entries[0].file_size > MAX_COMPARISON_BYTES:
                raise ComparisonDataError("三策略比较元数据超过2MB限制")
            comparison = decode_comparison(archive.read(entries[0]), run.run_id)
        validate_selected_run(comparison, run)
    except (ComparisonDataError, BadZipFile, KeyError, TypeError, ValueError, RuntimeError, ZlibError) as exc:
        return SharedBundle(run, comparison_error=str(exc))
    return SharedBundle(run, comparison)


def load_shared_run(stations: pd.DataFrame, path: str | Path | None = None) -> RunData | None:
    """Compatibility API for the latest complete single simulation."""
    return load_shared_bundle(stations, path).run
