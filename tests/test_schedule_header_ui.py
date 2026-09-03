from pathlib import Path


def test_today_marker_does_not_change_desktop_header_or_card_geometry() -> None:
    root = Path(__file__).parents[1]
    script = (root / "static" / "app.js").read_text(encoding="utf-8")
    styles = (root / "static" / "styles.css").read_text(encoding="utf-8")

    assert 'element("span","today-marker","Сегодня")' in script
    assert 'heading.append(element("strong","",dayNames[day]))' in script
    assert ".day-heading { position:relative; height:25px" in styles
    assert ".today-marker { position:absolute" in styles
    assert "bottom:calc(100% + 1px)" in styles
    assert ".schedule-grid { display:grid" in styles and "padding-top:16px" in styles
