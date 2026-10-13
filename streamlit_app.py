"""Streamlit Community Cloud entry point."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
import runpy

runpy.run_path(str(Path(__file__).parent / "src" / "pmtracker" / "app.py"), run_name="__main__")
