from dataclasses import dataclass


@dataclass(frozen=True)
class LMSettings:
    model: str = "openai/gemma4:12b"
    api_base: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    temperature: float = 0.0
    max_tokens: int = 4096


DEFAULT_LM_SETTINGS = LMSettings()

