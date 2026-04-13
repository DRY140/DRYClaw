from __future__ import annotations

import plistlib
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from croniter import croniter


LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LOG_DIR = Path.home() / ".dryclaw" / "logs"


@dataclass
class ScheduleItem:
    id: str
    name: str
    cron: str
    prompt: str
    plist: Path


class LaunchdScheduler:
    def __init__(self) -> None:
        LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def create(self, cron_expr: str, prompt: str, name: str = "") -> ScheduleItem:
        schedule_id = name.strip() or uuid4().hex[:8]
        label = f"com.dryclaw.schedule.{schedule_id}"
        plist_path = LAUNCH_AGENTS_DIR / f"{label}.plist"

        payload = {
            "Label": label,
            "ProgramArguments": [sys.executable, "-m", "dryclaw", "-y", "-p", prompt],
            "RunAtLoad": False,
            "StandardOutPath": str(LOG_DIR / f"schedule-{schedule_id}.log"),
            "StandardErrorPath": str(LOG_DIR / f"schedule-{schedule_id}.log"),
        }

        calendar = self._cron_to_calendar(cron_expr)
        if calendar is not None:
            payload["StartCalendarInterval"] = calendar
        else:
            payload["StartInterval"] = max(60, self._cron_to_interval(cron_expr))

        with plist_path.open("wb") as f:
            plistlib.dump(payload, f)

        self._launchctl("load", plist_path)
        return ScheduleItem(id=schedule_id, name=label, cron=cron_expr, prompt=prompt, plist=plist_path)

    def list(self) -> list[ScheduleItem]:
        items: list[ScheduleItem] = []
        for path in sorted(LAUNCH_AGENTS_DIR.glob("com.dryclaw.schedule.*.plist")):
            try:
                data = plistlib.loads(path.read_bytes())
                label = str(data.get("Label", path.stem))
                schedule_id = label.rsplit(".", 1)[-1]
                args = data.get("ProgramArguments") or []
                prompt = str(args[-1]) if args else ""
                cron = self._calendar_to_hint(data)
                items.append(ScheduleItem(id=schedule_id, name=label, cron=cron, prompt=prompt, plist=path))
            except Exception:
                continue
        return items

    def delete(self, schedule_id: str) -> bool:
        label = f"com.dryclaw.schedule.{schedule_id.strip()}"
        path = LAUNCH_AGENTS_DIR / f"{label}.plist"
        if not path.exists():
            return False

        self._launchctl("unload", path)
        path.unlink(missing_ok=True)
        return True

    @staticmethod
    def _cron_to_calendar(cron_expr: str) -> dict[str, int] | list[dict[str, int]] | None:
        fields = cron_expr.split()
        if len(fields) != 5:
            return None

        minute, hour, dom, month, dow = fields

        def parse(v: str, key: str) -> dict[str, int] | None:
            if v == "*":
                return None
            if v.isdigit():
                return {key: int(v)}
            return None

        parts = [parse(minute, "Minute"), parse(hour, "Hour"), parse(dom, "Day"), parse(month, "Month"), parse(dow, "Weekday")]
        if any(p is None and field != "*" for p, field in zip(parts, fields)):
            return None

        merged: dict[str, int] = {}
        for p in parts:
            if p:
                merged.update(p)
        return merged if merged else None

    @staticmethod
    def _cron_to_interval(cron_expr: str) -> int:
        base = datetime.now()
        it = croniter(cron_expr, base)
        first = it.get_next(datetime)
        second = it.get_next(datetime)
        return int((second - first).total_seconds())

    @staticmethod
    def _calendar_to_hint(data: dict) -> str:
        if "StartInterval" in data:
            return f"interval:{data['StartInterval']}s"
        if "StartCalendarInterval" in data:
            return str(data["StartCalendarInterval"])
        return "unknown"

    @staticmethod
    def _launchctl(action: str, plist_path: Path) -> None:
        try:
            subprocess.run(["launchctl", action, str(plist_path)], check=False, capture_output=True)
        except Exception:
            pass
