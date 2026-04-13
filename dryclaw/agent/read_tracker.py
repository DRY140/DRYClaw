from __future__ import annotations

from pathlib import Path


class ReadTracker:
    """记录已读文件集合，用于执行 file_edit 前的读前写保护。"""

    def __init__(self) -> None:
        self._read_files: set[str] = set() # 集合 数据类型

    @staticmethod
    # 小工具 标准化路径，转化为/user开头的绝对路径
    def _normalize(path: str) -> str:
        return str(Path(path).expanduser().resolve())

    # 标记 已读 文件路径，存入集合
    def mark_read(self, path: str) -> None:
        self._read_files.add(self._normalize(path))

    # 判断是否已读
    def is_read(self, path: str) -> bool:
        normalized = self._normalize(path)
        if normalized.endswith("/MEMORY.md"):
            return True
        return normalized in self._read_files
