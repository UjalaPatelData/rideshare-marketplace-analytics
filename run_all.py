"""Runs the full pipeline: generate synthetic marketplace data -> clean -> SQL -> analysis and reports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
import analyze, generate_data  # noqa: E402

if __name__ == "__main__":
    generate_data.main()
    analyze.main()
