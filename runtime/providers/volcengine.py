from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .base import LLMProvider, ProviderError, ProviderUnavailable


class VolcengineProvider(LLMProvider):
    """Volcengine Ark adapter implementing the provider-neutral LLM port."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 150,
    ) -> None:
        self.api_key = api_key or os.getenv("VOLCENGINE_API_KEY") or os.getenv("ARK_API_KEY")
        self.model = model or os.getenv("VOLCENGINE_ENDPOINT_ID") or os.getenv("ARK_ENDPOINT_ID")
        self.base_url = (base_url or os.getenv("VOLCENGINE_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        if not self.configured:
            raise ProviderUnavailable(
                "未配置火山引擎模型。请设置 VOLCENGINE_API_KEY（或 ARK_API_KEY）和 "
                "VOLCENGINE_ENDPOINT_ID（或 ARK_ENDPOINT_ID）。"
            )

        responses_api = self.base_url.lower().endswith("/responses")
        chat_api = self.base_url.lower().endswith("/chat/completions")
        url = self.base_url if responses_api or chat_api else f"{self.base_url}/chat/completions"
        if responses_api:
            payload: dict[str, Any] = {
                "model": self.model,
                "instructions": system,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": user}]}],
                "max_output_tokens": max_tokens,
                "thinking": {"type": "disabled"},
            }
        else:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
                detail = parsed.get("error", {}).get("message") or detail
            except json.JSONDecodeError:
                pass
            raise ProviderError(f"火山引擎请求失败（{exc.code}）：{detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(f"无法连接火山引擎：{exc}") from exc

        text = self._extract_text(data, responses_api)
        if not text:
            raise ProviderError("火山引擎没有返回可用文本。")
        return text

    @staticmethod
    def _extract_text(data: dict[str, Any], responses_api: bool) -> str:
        if not responses_api:
            choices = data.get("choices") or []
            if choices and isinstance(choices[0], dict):
                content = (choices[0].get("message") or {}).get("content")
                return content.strip() if isinstance(content, str) else ""
            return ""

        direct = data.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        parts: list[str] = []
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    value = content.get("text")
                    if isinstance(value, str):
                        parts.append(value)
        return "\n".join(parts).strip()
