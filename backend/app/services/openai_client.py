from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.services.llm_client import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.3,
        max_output_tokens: int = 4000,
    ) -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    async def generate_plan(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raw_text = await self._generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
        )

        try:
            return self._extract_json(raw_text)
        except Exception as first_error:
            repaired_text = await self._repair_json(
                original_response=raw_text,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            try:
                return self._extract_json(repaired_text)
            except Exception as second_error:
                raise ValueError(
                    "openai_response_invalid_json | "
                    f"first_error={first_error} | second_error={second_error} | "
                    f"raw_response={raw_text[:3000]!r} | repaired_response={repaired_text[:3000]!r}"
                ) from second_error

    async def _generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        response = await self.client.responses.create(
            model=self.model,
            temperature=temperature,
            max_output_tokens=self.max_output_tokens,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        )

        text_output = self._extract_text_from_response(response)
        if not text_output:
            raise ValueError("openai_empty_response")

        return text_output.strip()

    async def _repair_json(
        self,
        *,
        original_response: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        repair_system_prompt = """
You repair model outputs into valid JSON.

Your only job:
- take the broken response
- preserve the intended meaning
- return valid JSON only

Rules:
- no markdown
- no code fences
- no explanations
- no commentary
- output a single valid JSON object only
- do not add new content unless needed to make the JSON structurally valid
""".strip()

        repair_user_prompt = f"""
The previous model output was supposed to be valid JSON but was not.

Original system prompt:
{system_prompt}

Original user prompt:
{user_prompt}

Broken response:
{original_response}

Return only repaired valid JSON.
""".strip()

        return await self._generate_text(
            system_prompt=repair_system_prompt,
            user_prompt=repair_user_prompt,
            temperature=0,
        )

    def _extract_text_from_response(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = getattr(response, "output", None)
        if isinstance(output, list):
            chunks: list[str] = []

            for item in output:
                content = getattr(item, "content", None)
                if not isinstance(content, list):
                    continue

                for part in content:
                    part_text = getattr(part, "text", None)
                    if isinstance(part_text, str) and part_text.strip():
                        chunks.append(part_text.strip())

            if chunks:
                return "\n".join(chunks).strip()

        try:
            response_dict = response.model_dump() if hasattr(response, "model_dump") else None
            if isinstance(response_dict, dict):
                text = self._extract_text_from_response_dict(response_dict)
                if text:
                    return text
        except Exception:
            pass

        return ""

    def _extract_text_from_response_dict(self, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = payload.get("output")
        if not isinstance(output, list):
            return ""

        chunks: list[str] = []

        for item in output:
            if not isinstance(item, dict):
                continue

            content = item.get("content")
            if not isinstance(content, list):
                continue

            for part in content:
                if not isinstance(part, dict):
                    continue

                part_text = part.get("text")
                if isinstance(part_text, str) and part_text.strip():
                    chunks.append(part_text.strip())

        return "\n".join(chunks).strip() if chunks else ""

    def _extract_json(self, text: str) -> dict[str, Any]:
        cleaned = self._strip_code_fences(text)

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        json_candidate = self._find_json_object(cleaned)
        if json_candidate is None:
            raise ValueError("json_object_not_found")

        parsed = json.loads(json_candidate)
        if not isinstance(parsed, dict):
            raise ValueError("json_root_must_be_object")

        return parsed

    def _strip_code_fences(self, text: str) -> str:
        stripped = text.strip()

        fenced_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL | re.IGNORECASE)
        if fenced_match:
            return fenced_match.group(1).strip()

        return stripped

    def _find_json_object(self, text: str) -> str | None:
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for index in range(start, len(text)):
            ch = text[index]

            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        return None