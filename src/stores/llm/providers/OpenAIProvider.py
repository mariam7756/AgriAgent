from ..LLMInterface import LLMInterface
from ..LLMEnums import OpenAIEnums
from openai import OpenAI
import logging


class OpenAIProvider(LLMInterface):

    def __init__(
        self,
        api_key: str,
        api_url: str = None,
        default_input_max_characters: int = 1000,
        default_generation_max_output_tokens: int = 1000,
        default_generation_temperature: float = 0.1
    ):

        self.api_key = api_key
        self.api_url = api_url

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None

        self.embedding_model_id = None
        self.embedding_size = None

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_url if self.api_url else None
        )

        self.enums = OpenAIEnums
        self.logger = logging.getLogger(__name__)


    # ------------------------
    # Models
    # ------------------------
    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id


    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size


    # ------------------------
    # Helpers
    # ------------------------
    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()


    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": self.process_text(prompt)
        }


    # ------------------------
    # Generation
    # ------------------------
    def generate_text(
        self,
        prompt: str,
        chat_history: list = None,
        max_output_tokens: int = None,
        temperature: float = None
    ):

        if not self.client:
            print("OpenAI client not initialized")
            return None

        if not self.generation_model_id:
            print("Generation model not set")
            return None


        if chat_history is None:
            chat_history = []

        max_output_tokens = (
            max_output_tokens
            if max_output_tokens
            else self.default_generation_max_output_tokens
        )

        temperature = (
            temperature
            if temperature is not None
            else self.default_generation_temperature
        )


        messages = chat_history.copy()

        messages.append(
            self.construct_prompt(
                prompt=prompt,
                role=OpenAIEnums.USER.value
            )
        )


        try:
            print("SENDING TO MODEL...")
            print("MODEL:", self.generation_model_id)

            response = self.client.chat.completions.create(
                model=self.generation_model_id,
                messages=messages,
                max_tokens=max_output_tokens,
                temperature=temperature
            )

        except Exception as e:
            print("API ERROR:", str(e))
            return None


        if (
            not response
            or not response.choices
            or len(response.choices) == 0
            or not response.choices[0].message
        ):
            print("Empty response")
            return None


        return response.choices[0].message.content


    # ------------------------
    # Embedding
    # ------------------------
    def embed_text(
        self,
        text: str,
        document_type: str = None
    ):

        if not self.client:
            print("Client not initialized")
            return None


        if not self.embedding_model_id:
            print("Embedding model not set")
            return None


        try:
            response = self.client.embeddings.create(
                model=self.embedding_model_id,
                input=text
            )

        except Exception as e:
            print("Embedding error:", str(e))
            return None


        if (
            not response
            or not response.data
            or len(response.data) == 0
        ):
            print("Empty embedding response")
            return None


        return response.data[0].embedding
    