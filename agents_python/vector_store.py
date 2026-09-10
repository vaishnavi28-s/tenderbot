from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, SparseVectorParams, Modifier, PointStruct, SparseVector
from litellm import embedding
from fastembed import SparseTextEmbedding
import uuid

COLLECTION_NAME = "tenders"
QDRANT_URL = "http://localhost:6333"

client = QdrantClient(url=QDRANT_URL)
sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")  # local, free, no API calls


def init_db():
    """Creates the hybrid (dense + sparse) collection if it doesn't exist."""
    try:
        collections = client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)

        if not exists:
            print(f"Creating hybrid collection: {COLLECTION_NAME}")
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={
                    "dense": VectorParams(size=3072, distance=Distance.COSINE),
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(modifier=Modifier.IDF),
                },
            )
    except Exception as e:
        print(f"Database init failed: {e}")


def build_searchable_text(dossier: dict) -> str:
    """Only the fields that matter for matching — not raw_content."""
    title = dossier.get("title") or ""
    sector = dossier.get("sector") or ""
    authority = dossier.get("contractingAuthority") or ""
    cpv = dossier.get("cpvCode") or "n/a"
    keywords_list = dossier.get("keywords") or []
    eligibility_list = dossier.get("eligibilityCriteria") or []
    summary = dossier.get("summary") or ""

    keywords = ", ".join(k for k in keywords_list if k)
    eligibility = "; ".join(e for e in eligibility_list if e)

    return (
        f"{title}. "
        f"Sector: {sector}. "
        f"Authority: {authority}. "
        f"CPV: {cpv}. "
        f"Keywords: {keywords}. "
        f"Eligibility: {eligibility}. "
        f"{summary}"
    )


async def save_to_vault(dossier: dict):
    """Saves a single processed dossier with both dense and sparse vectors."""
    try:
        searchable_text = build_searchable_text(dossier)

        dense_vector = await get_embedding(searchable_text)
        sparse_vector = next(sparse_model.embed([searchable_text]))

        id_source = dossier.get('link') or dossier.get('sourceUrl') or dossier.get('title') or 'unknown'

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, id_source)),
                    vector={
                        "dense": dense_vector,
                        "sparse": SparseVector(
                            indices=sparse_vector.indices.tolist(),
                            values=sparse_vector.values.tolist(),
                        ),
                    },
                    payload=dossier,
                )
            ]
        )
        print(f"Vaulted: {dossier.get('title')}")
    except Exception as e:
        print(f"Failed to vault {dossier.get('title')}: {e}")


async def get_embedding(text: str):
    try:
        response = embedding(model="gemini/gemini-embedding-001", input=[text])
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding failed for text: {text[:30]}... Error: {e}")
        return [0.0] * 3072