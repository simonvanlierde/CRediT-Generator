"""Lightweight image exporter for CRediT heatmaps."""

import base64
import contextlib
import io
from typing import Literal

import matplotlib as mpl
import numpy as np
import pandas as pd

# Set headless backend at import time (must happen before pyplot import)
mpl.use("Agg")

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import seaborn as sns

DEFAULT_TILE_COLOR = "#3d94d1"
ALLOWED_FORMATS = ("png", "pdf", "svg")


def _validate_matrix_shape(arr: np.ndarray, authors: list[str], roles: list[str]) -> None:
    if arr.ndim != 2:
        msg = f"matrix must be 2D, got shape {arr.shape}"
        raise ValueError(msg)
    expected = (len(authors), len(roles))
    if arr.shape != expected:
        msg = f"matrix shape {arr.shape} does not match authors/roles lengths {expected}"
        raise ValueError(msg)


def _validate_tile_color(tile_color: str) -> None:
    if not mcolors.is_color_like(tile_color):
        msg = f"invalid tile_color: {tile_color!r}"
        raise ValueError(msg)


def _compute_figsize(nrows: int, ncols: int, base: tuple[float, float]) -> tuple[float, float]:
    cell_inch = 0.35
    width = max(base[0], cell_inch * max(3, ncols) + 1.0)
    height = max(base[1], cell_inch * max(2, nrows) + 1.0)
    return width, height


def create_heatmap_bytes(
    table_data: list[dict],
    tile_color: str = DEFAULT_TILE_COLOR,
    figsize: tuple[float, float] = (10, 6),
    dpi: int = 150,
    save_format: Literal["png", "pdf", "svg"] = "png",
    *,
    transpose: bool = False,
) -> bytes:
    """Render a heatmap and return image bytes from Dash `table_data`.

    The function expects `table_data` produced by the Dash table (list of
    dicts). Role columns must be boolean-like (True/False). True maps to 100
    intensity, False maps to 0.
    """
    if not table_data:
        err_msg = "table_data must be a non-empty list of records"
        raise ValueError(err_msg)

    df = pd.DataFrame(table_data)
    with contextlib.suppress(KeyError, IndexError):
        df = df.drop(columns=df.columns[0], axis=1)

    # Build author display names with pandas built-ins; prefer full name, fall back to initials
    name_cols = ["First Name", "Middle Name", "Last Name"]
    existing_name_cols = [c for c in name_cols if c in df.columns]
    combined = df[existing_name_cols].fillna("").agg(" ".join, axis=1).str.strip()
    initials = df["Initials"].fillna("") if "Initials" in df.columns else pd.Series([""] * len(df))
    authors = combined.where(combined != "", initials).tolist()

    # roles are columns after the first four
    roles = list(df.columns[4:])

    # vectorized boolean conversion for role columns, then scale to 0/100
    if roles:
        df_roles = df.loc[:, roles].fillna(False).astype(bool)
        arr = (df_roles.astype(int) * 100).to_numpy(dtype=float)
    else:
        arr = np.zeros((len(df), 0), dtype=float)
    _validate_matrix_shape(arr, authors, roles)
    _validate_tile_color(tile_color)

    fmt = save_format.lower()
    if fmt not in ALLOWED_FORMATS:
        msg = f"unsupported save_format: {save_format!r}"
        raise ValueError(msg)

    if transpose:
        arr = arr.T
        authors, roles = roles, authors

    nrows, ncols = arr.shape
    width, height = _compute_figsize(nrows, ncols, figsize)

    cmap = mcolors.LinearSegmentedColormap.from_list("accent", ["white", tile_color])

    fig, ax = plt.subplots(figsize=(width, height))
    try:
        sns.heatmap(
            arr,
            cmap=cmap,
            vmin=0,
            vmax=100,
            cbar=False,
            ax=ax,
            linewidths=0.5,
            linecolor="gray",
            square=True,
            annot=False,
        )
        ax.set_aspect("equal")

        ax.set_yticks(np.arange(len(authors)) + 0.5)
        ax.set_yticklabels(authors, rotation=0, va="center")
        ax.set_xticks(np.arange(len(roles)) + 0.5)
        ax.set_xticklabels(roles, rotation=45, ha="right")
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=dpi)
        buf.seek(0)
        return buf.getvalue()
    finally:
        plt.close(fig)


def create_heatmap_download(
    table_data: list[dict[str, str | bool]],
    filename: str,
    tile_color: str,
    *,
    save_format: Literal["png", "pdf", "svg"] = "png",
    transpose: bool = False,
) -> dict[str, str | bool]:
    """Create a base64 download payload for the requested format."""
    img_bytes = create_heatmap_bytes(table_data, tile_color=tile_color, save_format=save_format, transpose=transpose)
    b64 = base64.b64encode(img_bytes).decode("ascii")
    return {"content": b64, "filename": filename, "base64": True}
