from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_app_renders_offline_with_bundled_snapshot():
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60).run()
    assert not at.exception
    assert any("not forecasts or advice" in m.value for m in at.markdown)
    at.text_input[0].set_value("zzzz-no-match").run()
    assert not at.exception and any("No markets match" in i.value for i in at.info)
