from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from litellm import embedding
import uuid
import asyncio

COLLECTION_NAME = "tenders"
QDRANT_URL = "http://localhost:6333"

client = QdrantClient(url=QDRANT_URL)


def init_db():
    """Creates the collection if it doesn't exist."""
    try:
        collections = client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        
        if not exists:
            print(f"Creating collection: {COLLECTION_NAME}")
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
            )
    except Exception as e:
        print(f"Database init failed: {e}")

async def save_to_vault(dossier: dict):
    """Saves a single processed dossier from the Agent to Qdrant."""
    try:
        # Create searchable text from the agent's output
        searchable_text = f"{dossier.get('referenceNumber')}: {dossier.get('title')} from {dossier.get('contractingAuthority')}. CPV: {dossier.get('cpvCode') or 'n/a'}. {dossier.get('summary')}"
        
        # Get embedding
        vector = await get_embedding(searchable_text)
        
        # Upsert
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=dossier
                )
            ]
        )
        print(f"Vaulted: {dossier.get('title')}")
    except Exception as e:
        print(f"Failed to vault {dossier.get('title')}: {e}")

async def get_embedding(text: str):
    try:
        response = embedding(
            model="gemini/gemini-embedding-001", 
            input=[text]
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding failed for text: {text[:30]}... Error: {e}")
        return [0.0] * 3072


