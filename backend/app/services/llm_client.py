from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    @abstractmethod
    async def generate_plan(self, system_prompt: str, user_prompt: str) -> dict:
        raise NotImplementedError