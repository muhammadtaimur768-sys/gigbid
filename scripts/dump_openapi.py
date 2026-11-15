"""Write the FastAPI OpenAPI schema to apps/web/openapi.json (input for openapi-typescript)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MOUNT_GIGSIM", "0")
os.environ.setdefault("MOUNT_MCP", "0")

from apps.api.main import app  # noqa: E402

out = ROOT / "apps" / "web" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
spec = app.openapi()
out.write_text(json.dumps(spec, indent=2, sort_keys=False) + "\n")
print(f"wrote {out.relative_to(ROOT)} ({len(spec.get('paths', {}))} paths)")
