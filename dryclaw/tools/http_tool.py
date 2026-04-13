from __future__ import annotations

from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class HttpTool:
    name = "http" # 工具名称
    description = "Perform a controlled HTTP request" # 工具描述
    input_schema = { # 输入模式
        "type": "object", 
        "properties": { # 能传哪些参数
            "url": {"type": "string", "description": "HTTP URL"},
            "method": {"type": "string", "description": "HTTP method", "default": "GET"},
            "body": {"type": "string", "description": "Request body", "default": ""},
        },
        "required": ["url"],
    }

    def run(self, **kwargs) -> str:
        url = str(kwargs.get("url", "")).strip()
        method = str(kwargs.get("method", "GET")).upper()
        body = str(kwargs.get("body", ""))

        if not url:
            return "ERROR: missing url"

        try:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                return "ERROR: unsupported scheme"

            data = body.encode("utf-8") if body and method != "GET" else None
            req = Request(url=url, method=method, data=data)
            with urlopen(req, timeout=20) as resp:
                headers = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
                raw = resp.read(10240)
                body_text = raw.decode("utf-8", errors="replace")
                return (
                    f"Status: {resp.status} {getattr(resp, 'reason', '')}\n\n"
                    f"Headers:\n{headers}\n\n"
                    f"Body:\n{body_text}"
                )
        except HTTPError as exc:
            return f"ERROR: http error {exc.code}: {exc.reason}"
        except URLError as exc:
            return f"ERROR: url error: {exc.reason}"
        except Exception as exc:
            return f"ERROR: http request failed: {exc}"
