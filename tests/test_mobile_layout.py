from pathlib import Path


def test_mobile_dashboard_and_navigation_tracks_can_shrink_to_viewport() -> None:
    styles = (Path(__file__).parents[1] / "static" / "styles.css").read_text(encoding="utf-8")

    assert ".two-columns { display:grid; grid-template-columns:repeat(2,minmax(0,1fr))" in styles
    assert ".two-columns > *,.section-head { min-width:0; }" in styles
    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in styles
    assert ".two-columns,.study-layout,.settings-grid { grid-template-columns:minmax(0,1fr); }" in styles
