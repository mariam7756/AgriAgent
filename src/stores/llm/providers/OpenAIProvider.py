from ..LLMInterface import LLMInterface
from ..LLMEnums import OpenAIEnums
from openai import OpenAI
import logging
from typing import List, Union



class OpenAIProvider(LLMInterface):

    def __init__(
        self,
        api_key: str,
        api_url: str = None,
        default_input_max_characters: int = 8000,
        default_generation_max_output_tokens: int = 512,
        default_generation_temperature: float = 0.3,
    ):
        
        self.api_key = api_key
        self.api_url = api_url or "http://127.0.0.1:11434/v1"
        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature
        
        self.generation_model_id = None
        
        self.embedding_model_id = None
        
        self.embedding_size = None
        
        self.client = OpenAI(
            api_key=self.api_key or "ollama",
            base_url=self.api_url.rstrip("/"),
        )
        
        self.enums = OpenAIEnums
        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id
        

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text: str):
        return text[: self.default_input_max_characters].strip()

    def construct_prompt(self, prompt: str, role: str):
        return {"role": role, "content": self.process_text(prompt)}

    def generate_text(
        self,
        prompt: str = None,
        chat_history: list = None,
        max_output_tokens: int = None,
        temperature: float = None,
    ):
        if not self.client or not self.generation_model_id:
            return None


        if chat_history is None:
            chat_history = []

        max_output_tokens = max_output_tokens or self.default_generation_max_output_tokens
        temperature = temperature if temperature is not None else self.default_generation_temperature


        messages = chat_history.copy()
        
        if prompt:
            messages.append(self.construct_prompt(prompt, OpenAIEnums.USER.value))

        try:
            
            response = self.client.chat.completions.create(
                model=self.generation_model_id,
                messages=messages,
                max_tokens=max_output_tokens,
                temperature=temperature,
                stream=True,
                timeout=60,
            )
            full_response = ""
            for chunk in response:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full_response += delta
            return full_response.strip() if full_response else None
        except Exception as e:
            self.logger.error(f"LLM generation error: {e}")
            return None

    def embed_text(self, text: Union[str, List[str]], document_type: str = None):
        if not self.client or not self.embedding_model_id:
            return None
        

        single_input = isinstance(text, str)
        inputs = [text] if single_input else text
        

        try:
            response = self.client.embeddings.create(
                model=self.embedding_model_id,
                input=[self.process_text(t) for t in inputs],
            )
            
        except Exception as e:
            self.logger.error(f"Embedding error: {e}")
            return None

        if not response or not response.data:
            return None

        embeddings = [item.embedding for item in response.data]
        return embeddings[0] if single_input else embeddings