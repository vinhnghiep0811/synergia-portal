import logging
from typing import List

from huggingface_hub import login
from app.core.config import HF_TOKEN

try:
    from FlagEmbedding import FlagModel
except ImportError:
    FlagModel = None

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


class EmbeddingService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            cls._instance._initialize_model()
        return cls._instance

    def _initialize_model(self):
        if FlagModel is None:
            raise RuntimeError("FlagEmbedding is not installed.")

        if HF_TOKEN:
            try:
                login(token=HF_TOKEN, add_to_git_credential=False)
                logger.info("[embedding] Logged in to Hugging Face Hub.")
            except Exception as e:
                logger.warning("[embedding] HF login failed: %s", e)

        logger.info("[embedding] Loading model: %s", MODEL_NAME)

        try:
            self._model = FlagModel(
                MODEL_NAME,
                query_instruction_for_retrieval=(
                    "Represent this sentence for searching relevant passages: "
                ),
                use_fp16=False,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load embedding model: {e}") from e

        logger.info("[embedding] Model loaded successfully.")

    def generate_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text.")

        embedding = self._model.encode([text.strip()])[0].tolist()

        if len(embedding) != EMBEDDING_DIM:
            raise RuntimeError(f"Invalid embedding dim: {len(embedding)}")

        return embedding

    def generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = 32,
    ) -> List[List[float]]:
        if not texts:
            return []

        clean_texts = [t.strip() for t in texts]

        if any(not t for t in clean_texts):
            raise ValueError("Cannot embed empty chunk content.")

        results = []

        for i in range(0, len(clean_texts), batch_size):
            batch = clean_texts[i : i + batch_size]
            embeddings = self._model.encode(batch)

            for emb in embeddings:
                emb_list = emb.tolist()

                if len(emb_list) != EMBEDDING_DIM:
                    raise RuntimeError(f"Invalid embedding dim: {len(emb_list)}")

                results.append(emb_list)

        return results