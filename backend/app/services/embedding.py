import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate text embeddings via DashScope OpenAI-compatible API."""

    def __init__(self):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim

    async def embed(self, text: str) -> list[float] | None:
        """Generate embedding for a single text. Returns None on failure."""
        if not text or not self.api_key:
            return None
        text = text[:8000]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": text,
                        "dimensions": self.dim,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
        except Exception as e:
            logger.error("Embedding failed: %s", e)
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts. Chunks into batches of 10 for DashScope v3."""
        if not texts or not self.api_key:
            return [None] * len(texts)
        truncated = [t[:8000] for t in texts]
        BATCH_SIZE = 10  # DashScope text-embedding-v3 per-request cap
        out: list[list[float] | None] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for start in range(0, len(truncated), BATCH_SIZE):
                chunk = truncated[start:start + BATCH_SIZE]
                try:
                    response = await client.post(
                        f"{self.base_url}/embeddings",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "input": chunk,
                            "dimensions": self.dim,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    out.extend(item["embedding"] for item in data["data"])
                except Exception as e:
                    logger.error(
                        "Batch embedding failed (batch %d-%d): %s",
                        start, start + len(chunk), e,
                    )
                    out.extend([None] * len(chunk))
        return out


embedding_service = EmbeddingService()
