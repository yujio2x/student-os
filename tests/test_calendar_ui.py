from pathlib import Path


def test_mobile_calendar_uses_stacked_event_bars_with_overflow_count() -> None:
    root = Path(__file__).parents[1]
    script = (root / "static" / "app.js").read_text(encoding="utf-8")
    styles = (root / "static" / "styles.css").read_text(encoding="utf-8")

    assert "events.slice(0,2)" in script
    assert 'element("span","calendar-more",`+${events.length-visible.length}`)' in script
    assert "item.subject||item.title" in script
    assert 'event.addEventListener("click",()=>openDeadlineDialog(item))' in script
    assert ".calendar-event { min-height:20px" in styles
    assert "font-size:0" not in styles
