from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .parser import parse_json_robust


@dataclass
class ModelResponse:
    text: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0


class BaseLLMAdapter:
    model_name: str
    allow_heuristic_fallback: bool = False

    def __init__(self):
        self.last_response: Optional[ModelResponse] = None

    def generate_text(self, prompt: str) -> ModelResponse:
        raise NotImplementedError

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        response = self.generate_text(prompt)
        self.last_response = response
        return parse_json_robust(response.text)


class OllamaAdapter(BaseLLMAdapter):
    def __init__(self, model_name: str, base_url: str | None = None):
        super().__init__()
        if not model_name:
            raise RuntimeError("Ollama model_name is required.")
        self.model_name = model_name

        resolved_base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        if not resolved_base_url:
            raise RuntimeError("OLLAMA_BASE_URL is required. Set it in .env.")
        self.base_url = resolved_base_url.rstrip("/")

    def generate_text(self, prompt: str) -> ModelResponse:
        import requests

        start = time.perf_counter()
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
            },
            timeout=60,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        if resp.status_code != 200:
            raise RuntimeError(f"Ollama request failed: {resp.status_code} {resp.text[:200]}")

        payload = resp.json()
        text = payload.get("response", "")
        prompt_eval_count = payload.get("prompt_eval_count", 0)
        eval_count = payload.get("eval_count", 0)
        return ModelResponse(
            text=text,
            latency_ms=latency_ms,
            prompt_tokens=prompt_eval_count,
            completion_tokens=eval_count,
            estimated_cost_usd=0.0,
        )


class OpenAIAdapter(BaseLLMAdapter):
    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
        timeout: int = 60,
    ):
        super().__init__()
        if not model_name:
            raise RuntimeError("OpenAI model_name is required.")
        self.model_name = model_name

        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise RuntimeError("OPENAI_API_KEY is required. Add it to .env or export it before running.")
        self.api_key = resolved_api_key

        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        self.base_url = resolved_base_url.rstrip("/")

        resolved_effort = reasoning_effort or os.getenv("OPENAI_REASONING_EFFORT", "").strip()
        self.reasoning_effort = resolved_effort or None
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, prompt: str, text_format: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "input": prompt,
        }
        if text_format is not None:
            payload["text"] = {"format": text_format}
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        return payload

    def _extract_output_text(self, payload: Dict[str, Any]) -> str:
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct

        fragments = []
        for item in payload.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict) or content.get("type") != "output_text":
                    continue
                text = content.get("text", "")
                if isinstance(text, str) and text:
                    fragments.append(text)

        if fragments:
            return "\n".join(fragments)

        raise RuntimeError("OpenAI response did not include any output text.")

    def _request(self, payload: Dict[str, Any]) -> ModelResponse:
        import requests

        start = time.perf_counter()
        resp = requests.post(
            f"{self.base_url}/responses",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        if resp.status_code >= 400:
            try:
                error_payload = resp.json()
            except ValueError:
                error_payload = {"error": {"message": resp.text[:500]}}
            error_message = error_payload.get("error", {}).get("message", resp.text[:500])
            raise RuntimeError(f"OpenAI request failed: {resp.status_code} {error_message}")

        response_payload = resp.json()
        usage = response_payload.get("usage", {})
        return ModelResponse(
            text=self._extract_output_text(response_payload),
            latency_ms=latency_ms,
            prompt_tokens=int(usage.get("input_tokens", 0) or 0),
            completion_tokens=int(usage.get("output_tokens", 0) or 0),
            estimated_cost_usd=0.0,
        )

    def generate_text(self, prompt: str) -> ModelResponse:
        return self._request(self._build_payload(prompt))

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        response = self._request(self._build_payload(prompt, text_format={"type": "json_object"}))
        self.last_response = response
        return parse_json_robust(response.text)


class EchoAdapter(BaseLLMAdapter):
    """Deterministic fallback adapter for offline or test mode."""

    def __init__(self):
        super().__init__()
        self.model_name = "echo"
        self.allow_heuristic_fallback = True

    def generate_text(self, prompt: str) -> ModelResponse:
        command = ""
        match = re.search(r"(?:User command|Input command):\s*(.*?)\n\n", prompt, flags=re.S)
        if match:
            command = match.group(1).strip()
        lowered = command.lower()

        subtasks = []
        sid = 1

        if "토마토" in command and ("썰" in command or "slice" in lowered):
            subtasks.append(
                {
                    "subtask_id": f"S{sid}",
                    "task_type": "slice_and_store",
                    "description": "토마토를 썰어서 냉장고에 넣기",
                    "required_skills": ["navigate", "slice", "pickup", "place", "open_close"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"source_object": "Tomato", "target_object": "Fridge"},
                    "code_draft": "navigate(source); slice(source); pickup(source_sliced); navigate(target); open(target); place(target)",
                }
            )
            sid += 1

        if "불" in command or "light" in lowered:
            action = "끄기"
            if "켜" in command or " on " in f" {lowered} ":
                action = "켜기"
            subtasks.append(
                {
                    "subtask_id": f"S{sid}",
                    "task_type": "toggle_light",
                    "description": f"불 {action}",
                    "required_skills": ["navigate", "toggle"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"action": action},
                    "code_draft": "navigate(LightSwitch); toggle(LightSwitch)",
                }
            )
            sid += 1

        if "데우" in command or "heat" in lowered:
            subtasks.append(
                {
                    "subtask_id": f"S{sid}",
                    "task_type": "heat_object",
                    "description": "빵을 전자레인지로 데우기",
                    "required_skills": ["navigate", "pickup", "open_close", "toggle", "place"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"object": "Bread"},
                    "code_draft": "navigate(Bread); pickup(Bread); navigate(Microwave); open(Microwave); place(Microwave); toggle(Microwave)",
                }
            )
            sid += 1

        if "씻" in command or "clean" in lowered:
            subtasks.append(
                {
                    "subtask_id": f"S{sid}",
                    "task_type": "clean_object",
                    "description": "접시를 싱크에서 세척하기",
                    "required_skills": ["navigate", "pickup", "toggle", "place"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"object": "Plate"},
                    "code_draft": "navigate(Plate); pickup(Plate); navigate(SinkBasin); place(SinkBasin); toggle(Faucet)",
                }
            )
            sid += 1

        if not subtasks:
            subtasks.append(
                {
                    "subtask_id": "S1",
                    "task_type": "navigate",
                    "description": "목표 위치로 이동",
                    "required_skills": ["navigate"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"target_object": "CounterTop"},
                    "code_draft": "navigate(target)",
                }
            )

        output = {"subtasks": subtasks}
        return ModelResponse(text=json.dumps(output, ensure_ascii=False), latency_ms=0)


def build_adapter(provider: str, model: str) -> BaseLLMAdapter:
    provider_norm = provider.lower()
    if provider_norm == "openai":
        return OpenAIAdapter(model_name=model)
    if provider_norm == "ollama":
        return OllamaAdapter(model_name=model)
    if provider_norm in {"echo", "mock", "offline"}:
        return EchoAdapter()
    raise ValueError(f"Unsupported provider: {provider}. Use 'openai', 'ollama', or 'echo'.")
