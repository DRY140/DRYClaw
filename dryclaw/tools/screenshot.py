from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


class ScreenshotTool:
    name = "screenshot"
    description = "Capture macOS screen and return compressed JPEG base64"
    input_schema = {
        "type": "object",
        "properties": {
            "quality": {"type": "integer", "description": "JPEG quality", "default": 85},
            "max_edge": {"type": "integer", "description": "Max image edge", "default": 1200},
            "save_path": {"type": "string", "description": "保存截图到指定路径（可选）", "default": ""},
        },
    }

    def run(self, **kwargs: Any) -> str:
        quality = int(kwargs.get("quality", 85) or 85)
        max_edge = int(kwargs.get("max_edge", 1200) or 1200)
        save_path = str(kwargs.get("save_path", "") or "").strip()

        with tempfile.TemporaryDirectory(prefix="dryclaw_shot_") as td:
            raw = Path(td) / "raw.png"
            out = Path(td) / "compressed.jpg"

            try:
                subprocess.run(["screencapture", "-x", str(raw)], check=True, capture_output=True)
            except Exception as exc:
                return f"ERROR: screencapture failed: {exc}"

            try:
                img = Image.open(raw)
                img.thumbnail((max_edge, max_edge))
                img.convert("RGB").save(out, format="JPEG", quality=quality)
                payload = base64.b64encode(out.read_bytes()).decode("utf-8")
                data: dict[str, Any] = {
                    "format": "jpeg",
                    "width": img.width,
                    "height": img.height,
                    "base64": payload,
                }

                # 保存到指定路径
                if save_path:
                    dst = Path(save_path)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.copy2(str(out), str(dst))
                    data["saved_to"] = str(dst)

                return json.dumps(data, ensure_ascii=False)
            except Exception as exc:
                return f"ERROR: image compress failed: {exc}"
