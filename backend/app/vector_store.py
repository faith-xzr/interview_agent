from pathlib import Path
from typing import Dict, List

from app.text_utils import cosine_similarity, hash_embedding


class HashingEmbeddingFunction:
    def __call__(self, input: List[str]) -> List[List[float]]:
        return [hash_embedding(text) for text in input]


class VectorStore:
    def __init__(self, persist_dir: Path, enable_chroma: bool = True) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._memory: Dict[str, Dict[str, str]] = {}
        self._collection = None
        if enable_chroma:
            try:
                import chromadb

                client = chromadb.PersistentClient(path=str(self.persist_dir))
                self._collection = client.get_or_create_collection(
                    name="recruiting_demo",
                    embedding_function=HashingEmbeddingFunction(),
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception:
                self._collection = None

    def add_document(self, run_id: str, owner_id: str, source: str, text: str) -> None:
        chunks = _chunk_text(text)
        if not chunks:
            return
        ids = [f"{run_id}:{owner_id}:{index}" for index, _ in enumerate(chunks)]
        metadatas = [{"run_id": run_id, "owner_id": owner_id, "source": source} for _ in chunks]
        if self._collection is not None:
            self._collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        for item_id, chunk in zip(ids, chunks):
            self._memory[item_id] = {"text": chunk, "run_id": run_id, "owner_id": owner_id, "source": source}

    def query(self, run_id: str, owner_id: str, query_text: str, limit: int = 5) -> List[str]:
        if self._collection is not None:
            try:
                result = self._collection.query(
                    query_texts=[query_text],
                    n_results=limit,
                    where={"$and": [{"run_id": run_id}, {"owner_id": owner_id}]},
                )
                return [doc for doc in (result.get("documents") or [[]])[0] if doc]
            except Exception:
                pass
        query_vector = hash_embedding(query_text)
        scored = []
        for item in self._memory.values():
            if item["run_id"] == run_id and item["owner_id"] == owner_id:
                scored.append((cosine_similarity(query_vector, hash_embedding(item["text"])), item["text"]))
        scored.sort(reverse=True, key=lambda pair: pair[0])
        return [text for _, text in scored[:limit]]


def _chunk_text(text: str, size: int = 480, overlap: int = 80) -> List[str]:
    normalized = text.strip()
    if not normalized:
        return []
    chunks = []
    start = 0
    while start < len(normalized):
        chunk = normalized[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        start += max(1, size - overlap)
    return chunks

