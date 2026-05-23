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
        self.api_url = api_url or"http://172.20.0.1:11434/v1"

        # Increased default truncation limit to avoid cutting off RAG context
        self.default_input_max_characters = 8000
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None
        
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = OpenAI(
            api_key=self.api_key or "ollama",
            base_url=self.api_url.rstrip("/")
        )

        self.enums = OpenAIEnums
        self.logger = logging.getLogger(__name__)



    # Models
    
    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id


    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size


    
    # Helpers
    
    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()


    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": self.process_text(prompt)
        }


    
    # Generation
    
    def generate_text(
        self,
        prompt: str,
        chat_history: list = None,
        max_output_tokens: int = None,
        temperature: float = None
    ):

        if not self.client:
            self.logger.error("Client not initialized")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation model not set")
            return None


        if chat_history is None:
            chat_history = []

        max_output_tokens = max_output_tokens or self.default_generation_max_output_tokens
        temperature = temperature if temperature is not None else self.default_generation_temperature

        messages = chat_history.copy()

        messages.append(
            self.construct_prompt(prompt, OpenAIEnums.USER.value)
        )


        try:
            
            response = self.client.chat.completions.create(
                model=self.generation_model_id,
                messages=messages,
                max_tokens=max_output_tokens,
                temperature=temperature
            )
            

        except Exception as e:
            self.logger.error(f"LLM API error: {str(e)}")
            return None

        if not response or not response.choices:
            self.logger.error("Empty response from LLM")
            return None
        

        return response.choices[0].message.content



    # Embedding
    
    def embed_text(self, text: str, document_type: str = None):

        if not self.client:
            self.logger.error("Client not initialized")
            return None 
        
        
        

        if not self.embedding_model_id:
            self.logger.error("Embedding model not set")
            return None


        try:
            response = self.client.embeddings.create(
                model=self.embedding_model_id,
                input=text
            )

        except Exception as e:
            self.logger.error(f"Embedding error: {str(e)}")
            return None

        if not response or not response.data:
            return None


        return response.data[0].embedding