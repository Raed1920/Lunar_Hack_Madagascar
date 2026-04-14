from functools import lru_cache
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptHub:
    @staticmethod
    @lru_cache(maxsize=128)
    def _load_template(prompt_name: str) -> str:
        path = PROMPTS_DIR / prompt_name
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    def render(self, prompt_name: str, **kwargs: str) -> str:
        template = self._load_template(prompt_name)
        if not kwargs:
            return template
        return template.format(**kwargs)
