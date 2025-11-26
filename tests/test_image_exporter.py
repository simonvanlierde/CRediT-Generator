"""Tests for the image exporter.

These are basic smoke tests that validate byte output for common
formats and error handling.
"""

from typing import Final

from app import image_exporter as exporter

SVG_START: Final = "<svg"
XML_DECL: Final = "<?xml"


def tiny_matrix() -> list[list[int]]:
    """Return a small 2x3 matrix used by tests."""
    return [[0, 50, 100], [25, 75, 0]]


def tiny_table_data() -> list[dict]:
    """Return a small table-data (list of records) with two authors and three roles."""
    cols = ["Role", "First Name", "Middle Name", "Last Name", "Initials", "Conceptualization", "Data Curation", "Writing"]
    return [
        {cols[0]: 1, cols[1]: "Alice", cols[2]: "", cols[3]: "", cols[4]: "A", cols[5]: True, cols[6]: False, cols[7]: True},
        {cols[0]: 2, cols[1]: "Bob", cols[2]: "", cols[3]: "", cols[4]: "B", cols[5]: False, cols[6]: True, cols[7]: False},
    ]


def test_create_png_bytes_basic() -> None:
    """create_heatmap_bytes returns non-empty PNG bytes for valid input."""
    table = tiny_table_data()

    b = exporter.create_heatmap_bytes(table, tile_color="#336699", save_format="png")
    assert isinstance(b, (bytes, bytearray))
    assert len(b) > 0


def test_create_pdf_bytes_basic() -> None:
    """create_heatmap_bytes returns non-empty PDF bytes for valid input."""
    table = tiny_table_data()

    b = exporter.create_heatmap_bytes(table, tile_color="#336699", save_format="pdf")
    assert isinstance(b, (bytes, bytearray))
    assert len(b) > 0


def test_create_svg_bytes_basic() -> None:
    """create_heatmap_bytes returns SVG bytes (contains <svg or XML decl)."""
    table = tiny_table_data()

    b = exporter.create_heatmap_bytes(table, tile_color="#336699", save_format="svg")
    assert isinstance(b, (bytes, bytearray))
    # SVG is XML text; ensure it starts with an XML/doctype or <svg
    txt = b.decode("utf-8", errors="ignore").lower()
    assert SVG_START in txt or XML_DECL in txt


def test_empty_table_raises() -> None:
    """Passing an empty table_data should raise ValueError."""
    try:
        exporter.create_heatmap_bytes([], tile_color="#336699", save_format="png")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_invalid_tile_color_raises() -> None:
    """An invalid tile_color triggers ValueError."""
    table = tiny_table_data()

    try:
        exporter.create_heatmap_bytes(table, tile_color="not-a-color", save_format="png")
        raised = False
    except ValueError:
        raised = True
    assert raised
