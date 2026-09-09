import logging  # noqa: N999

from openai import OpenAI

from ..LLMEnums import OpenAIEnums
from ..LLMInterface import LLMInterface


class OpenAIProvider(LLMInterface):

    def __init__(self, api_key: str, api_url: str | None = None,
                 default_input_max_char: int = 1000,
                 default_generation_output_tokens: int = 1000,
                 default_generation_temp: float = 0.1):

        self.api_key = api_key
        self.api_url = api_url
        self.default_input_max_char = default_input_max_char
        self.default_generation_output_tokens = default_generation_output_tokens
        self.default_generation_temp = default_generation_temp

        self.generation_model_id: str | None = None
        self.embedding_model_id: str | None = None
        self.embedding_size: int | None = None

        if self.api_url:
            self.client = OpenAI(api_key=self.api_key, base_url=self.api_url)
        else:
            self.client = OpenAI(api_key=self.api_key)  

        self.enum = OpenAIEnums
        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text: str):
        return text[:self.default_input_max_char].strip()

    def generate_text(self, prompt: str, chat_history: list | None = None,
                              max_output_tokens: int | None = None, temp: float | None = None):
        if not self.client:
            self.logger.error("OpenAI Client was not set")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation Model for OpenAI was not set")
            return None

        max_output_tokens = max_output_tokens if max_output_tokens else self.default_generation_output_tokens
        temp = temp if temp else self.default_generation_temp

        if chat_history is None:
            chat_history= []

        chat_history.append(
            self.construct_prompt(role=OpenAIEnums.USER.value , prompt=prompt)
        )

        response = self.client.chat.completions.create(
            model = self.generation_model_id,
            messages = chat_history,
            max_tokens = max_output_tokens,
            temperature = temp
        )

        if not response or not response.choices or len(response.choices) == 0 or not response.choices[0].message:
            self.logger.error("Error while generating text with openai")
            return None
        
        return response.choices[0].message.content

    def embed_text(self, text: str, document_type: str | None = None):

        if not self.client:
            self.logger.error("OpenAI Client was not set")
            return None

        if not self.embedding_model_id:
            self.logger.error("Embedding Model for OpenAI was not set")
            return None

        response = self.client.embeddings.create(
            model = self.embedding_model_id,
            input = text
        )

        if not response or not response.data or len(response.data) == 0 or not response.data[0].embedding:
            self.logger.error("Error while embedding text with OpenAI")
            return None

        return response.data[0].embedding

    def embed_batch_texts(self, texts: list[str], document_type: str | None = None):

        if not self.client or not self.embedding_model_id:
            self.logger.error("OpenAI Client or Model not set")
            return None

        response = self.client.embeddings.create(
            model=self.embedding_model_id,
            input=texts
        )

        if not response or not response.data or len(response.data) == 0:
            self.logger.error("Error while embedding batch texts with OpenAI")
            return None

        return [item.embedding for item in response.data]

    def construct_prompt(self, prompt:str, role:str):
        return {
            "role" : role,
            "content" : prompt
        }