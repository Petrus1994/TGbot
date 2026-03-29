from __future__ import annotations

import json
import re

from openai import AsyncOpenAI


class OpenAIClient:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_plan(self, system_prompt: str, user_prompt: str) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,  # меньше рандома → стабильнее JSON
        )

        content = response.choices[0].message.content

        return self._parse_json(content)

    def _parse_json(self, content: str) -> dict:
        """
        Пытаемся безопасно извлечь JSON из ответа модели
        """

        if not content:
            raise Exception("Empty response from AI")

        content = content.strip()

        # 1. если нормальный JSON
        try:
            return json.loads(content)
        except Exception:
            pass

        # 2. если JSON в ```json ```
        code_block_match = re.search(r"```json(.*?)```", content, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except Exception:
                pass

        # 3. если JSON просто в ``` ```
        code_block_match = re.search(r"```(.*?)```", content, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except Exception:
                pass

        # 4. если JSON где-то внутри текста
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except Exception:
                pass

        # 5. полный фейл
        raise Exception(f"Invalid JSON from AI:\n{content}")