from .LLMEnums import LLMEnums
from .providers import OpenAIProvider, CoHereProvider


class LLMProviderFactory:
    def __init__(self, config):
        self.config = config

    def create(self, provider: str, is_embedding: bool = False):
        if provider == LLMEnums.OPENAI.value:
            # embedding → Ollama local, generation → Groq
            api_url = self.config.EMBEDDING_API_URL if is_embedding else self.config.OPENAI_API_URL
            api_key = self.config.EMBEDDING_API_KEY if is_embedding else self.config.OPENAI_API_KEY
            return OpenAIProvider(
                api_key=api_key,
                api_url=api_url,
                default_input_max_characters=self.config.INPUT_DAFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=self.config.GENERATION_DAFAULT_MAX_TOKENS,
                default_generation_temperature=self.config.GENERATION_DAFAULT_TEMPERATURE,
            )

        if provider == LLMEnums.COHERE.value:
            return CoHereProvider(
                api_key=self.config.COHERE_API_KEY,
                default_input_max_characters=self.config.INPUT_DAFAULT_MAX_CHARACTERS,
                default_generation_max_output_tokens=self.config.GENERATION_DAFAULT_MAX_TOKENS,
                default_generation_temperature=self.config.GENERATION_DAFAULT_TEMPERATURE,
            )

        return None
    