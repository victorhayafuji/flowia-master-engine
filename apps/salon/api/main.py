"""
Salon API entrypoint.

Uso:
  uvicorn apps.salon.api.main:app --host 0.0.0.0 --port 8000
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import create_app  # noqa: E402

app = create_app()
