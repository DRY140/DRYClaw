from __future__ import annotations

import json


class ThinkTool:
    name = "think"
    description = "Internal reasoning scratchpad"
    input_schema = {
        "type": "object",
        "properties": {
            "thought": {"type": "string", "description": "Reasoning text"},
        },
        "required": ["thought"],
    }

    def run(self, **kwargs) -> str:
        # 该工具无副作用，唯一作用是给模型一个“显式规划”信号槽。
        thought = kwargs.get("thought")
        if isinstance(thought, str):
            return thought
        return json.dumps(kwargs, ensure_ascii=False)
