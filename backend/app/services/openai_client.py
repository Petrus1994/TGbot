from __future__ import annotations

import json
import re

from openai import AsyncOpenAI


class OpenAIClient:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )

        content = response.choices[0].message.content
        return self._parse_json(content)

    async def generate_plan(self, system_prompt: str, user_prompt: str) -> dict:
        return await self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,
        )

    def _parse_json(self, content: str) -> dict:
        if not content:
            raise Exception("Empty response from AI")

        content = content.strip()

        try:
            return json.loads(content)
        except Exception:
            pass

        code_block_match = re.search(r"```json(.*?)```", content, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except Exception:
                pass

        code_block_match = re.search(r"```(.*?)```", content, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except Exception:
                pass

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except Exception:
                pass

        raise Exception(f"Invalid JSON from AI:\n{content}")