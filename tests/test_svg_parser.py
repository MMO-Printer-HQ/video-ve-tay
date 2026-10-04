import pytest
import numpy as np
import whiteboard.svg_parser as svg_parser_module
from whiteboard.svg_parser import parse_svg, Stroke


def test_parse_simple_svg(tmp_path):
    svg_file = tmp_path / "simple.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 10 10 L 90 90" stroke="#000000" stroke-width="2"/>'
        '</svg>'
    )
    strokes = parse_svg(str(svg_file), canvas_width=800, canvas_height=600)
    assert len(strokes) >= 1
    s = strokes[0]
    assert isinstance(s, Stroke)
    assert len(s.points) > 10
    assert s.length > 0
    # Coordinates must fit within canvas
    assert np.all(s.points[:, 0] >= 0) and np.all(s.points[:, 0] <= 800)
    assert np.all(s.points[:, 1] >= 0) and np.all(s.points[:, 1] <= 600)


def test_parse_demo_svg():
    strokes = parse_svg("assets/demo_sketch.svg", canvas_width=1920, canvas_height=1080)
    assert len(strokes) > 0
    for s in strokes:
        assert len(s.points) >= 2
        assert s.length > 0
        assert np.all(s.points[:, 0] >= 0) and np.all(s.points[:, 0] <= 1920)
        assert np.all(s.points[:, 1] >= 0) and np.all(s.points[:, 1] <= 1080)


def test_stroke_color_and_width(tmp_path):
    svg_file = tmp_path / "styled.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 0 0 L 100 0" stroke="#ff0000" stroke-width="4"/>'
        '</svg>'
    )
    strokes = parse_svg(str(svg_file), canvas_width=1000, canvas_height=1000)
    assert len(strokes) == 1
    s = strokes[0]
    assert s.color == (255, 0, 0, 255)
    assert s.width > 0


def test_discontinuous_path_split(tmp_path):
    svg_file = tmp_path / "discontinuous.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 10 10 L 30 30 M 70 70 L 90 90" stroke="#000000" stroke-width="2"/>'
        '</svg>'
    )
    strokes = parse_svg(str(svg_file), canvas_width=800, canvas_height=600)
    # The discontinuous M commands must be split into separate strokes
    assert len(strokes) == 2


def test_shapes_conversion(tmp_path):
    svg_file = tmp_path / "shapes.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">'
        '<line x1="10" y1="10" x2="50" y2="50" stroke="#111111"/>'
        '<rect x="60" y="60" width="30" height="30" stroke="#222222"/>'
        '<circle cx="150" cy="150" r="20" stroke="#333333"/>'
        '</svg>'
    )
    strokes = parse_svg(str(svg_file), canvas_width=1000, canvas_height=1000)
    assert len(strokes) >= 3


def test_canvas_margin_and_centering(tmp_path):
    svg_file = tmp_path / "center.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 0 0 L 100 100" stroke="#000000"/>'
        '</svg>'
    )
    margin = 0.1
    strokes = parse_svg(str(svg_file), canvas_width=1000, canvas_height=1000, margin=margin)
    s = strokes[0]
    # With margin 0.1 on 1000x1000, stroke must be contained within [100, 900]
    assert np.all(s.points[:, 0] >= 100 - 1e-3)
    assert np.all(s.points[:, 0] <= 900 + 1e-3)
    assert np.all(s.points[:, 1] >= 100 - 1e-3)
    assert np.all(s.points[:, 1] <= 900 + 1e-3)


def test_missing_file_raises_error():
    with pytest.raises(FileNotFoundError):
        parse_svg("nonexistent_path_to_svg.svg")


def test_empty_svg_raises_error(tmp_path):
    empty_file = tmp_path / "empty.svg"
    empty_file.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    with pytest.raises(ValueError, match="No drawable paths"):
        parse_svg(str(empty_file))


def test_svg2paths_fallback_preserves_attributes(tmp_path, monkeypatch):
    svg_file = tmp_path / "fallback.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 10 10 L 90 90" stroke="#ff0000" stroke-width="6"/>'
        '</svg>'
    )
    # Simulate Document parsing failing to trigger the svg2paths fallback branch
    def fail_document(*args, **kwargs):
        raise RuntimeError("Simulated Document failure")

    monkeypatch.setattr(svg_parser_module, "Document", fail_document)

    strokes = parse_svg(str(svg_file), canvas_width=1000, canvas_height=1000)
    assert len(strokes) == 1
    s = strokes[0]
    # Color must be red, not default (30, 30, 30, 255)
    assert s.color == (255, 0, 0, 255)
    # Stroke width should be parsed from 6 and scaled, not default 4.0
    assert s.width > 4.0


def test_invisible_paths_skipped(tmp_path):
    svg_file = tmp_path / "invisible.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 0 0 L 50 50" stroke="none" fill="none"/>'
        '<path d="M 10 10 L 90 90" stroke="#000000" stroke-width="2"/>'
        '</svg>'
    )
    strokes = parse_svg(str(svg_file), canvas_width=800, canvas_height=600)
    # Only the visible path should be parsed
    assert len(strokes) == 1


def test_all_invisible_paths_raises_error(tmp_path):
    svg_file = tmp_path / "all_invisible.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 0 0 L 50 50" stroke="none" fill="none"/>'
        '</svg>'
    )
    with pytest.raises(ValueError, match="No drawable paths"):
        parse_svg(str(svg_file))


def test_inline_style_precedence_over_xml_attributes(tmp_path):
    """Verify inline style="..." declarations take precedence over direct XML attributes."""
    svg_file = tmp_path / "precedence.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 0 0 L 100 100" stroke="#0000ff" stroke-width="2" style="stroke: #ff0000; stroke-width: 8"/>'
        '</svg>'
    )
    strokes = parse_svg(str(svg_file), canvas_width=1000, canvas_height=1000)
    assert len(strokes) == 1
    # Color must be red from inline style, overriding direct stroke="#0000ff"
    assert strokes[0].color == (255, 0, 0, 255)

    # Also directly verify _parse_attr_dict precedence logic
    raw_attr = {
        "stroke": "#0000ff",
        "stroke-width": "2",
        "style": "stroke: #ff0000; stroke-width: 8",
    }
    parsed = svg_parser_module._parse_attr_dict(raw_attr)
    assert parsed["stroke"] == "#ff0000"
    assert parsed["stroke-width"] == "8"

