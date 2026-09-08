import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from qdrant_client import QdrantClient
from google import genai
from google.genai import types
from typing import List, Optional
import traceback
from sqlalchemy import create_engine, text
import litellm
import os
from fastapi.middleware.cors import CORSMiddleware


client_qdrant = QdrantClient(url="http://localhost:6333")
COLLECTION_NAME = "tenders"

client_gemini_embed = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

MODEL_LIST = [
    {"model": "gemini/gemini-3.6-flash", "api_key": os.getenv("GOOGLE_API_KEY")},
    {"model": "groq/openai/gpt-oss-120b", "api_key": os.getenv("GROQ_API_KEY")},
    {"model": "openrouter/meta-llama/llama-3.1-8b-instruct", "api_key": os.getenv("OPENROUTER_API_KEY")},
    {"model": "cerebras/gpt-oss-120b", "api_key": os.getenv("CEREBRAS_API_KEY")},
    {"model": "sambanova/Meta-Llama-3.1-8B-Instruct", "api_key": os.getenv("SAMBANOVA_API_KEY")}
]

engine = create_engine("postgresql://tender_admin:tender_secret@localhost:5433/tender_intel")
def sync_qdrant_to_sql():
    print("Syncing Qdrant vault to SQL archive...")
    points, _ = client_qdrant.scroll(collection_name=COLLECTION_NAME, limit=100, with_payload=True)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS historical_tenders"))
        conn.execute(text("""
            CREATE TABLE historical_tenders (
                id SERIAL PRIMARY KEY,
                title TEXT, sector TEXT, contractingAuthority TEXT, referenceNumber TEXT, url TEXT, quality_status TEXT
            )
        """))
        for p in points:
            pay = p.payload
            conn.execute(text("""
                INSERT INTO historical_tenders (title, sector, contractingAuthority, referenceNumber, url, quality_status)
                VALUES (:title, :sector, :contractingAuthority, :referenceNumber, :url, :quality_status)
            """), {
                "title": pay.get("title"), "sector": pay.get("sector"),
                "contractingAuthority": pay.get("contractingAuthority"), "referenceNumber": pay.get("referenceNumber"),
                "url": pay.get("URL"), "quality_status": pay.get("quality_status")
            })
        conn.commit()

sync_qdrant_to_sql()

# DATA MODELS
@strawberry.type
class FitReason:
    criterion: str
    status: str
    reason: str

@strawberry.type
class Tender:
    title: str
    contractingAuthority: str
    sector: str
    summary: str
    lat: float
    lng: float
    keywords: List[str]
    qualityStatus: str
    url: Optional[str]
    referenceNumber: Optional[str]
    submissionDeadline: Optional[str]
    estimatedValue: Optional[float]
    cpvCode: Optional[str]
    procedureType: Optional[str]
    eligibilityCriteria: List[str]
    fitTier: Optional[str]
    fitReasons: List[FitReason]
    factsVerified: Optional[bool]
    factCheckNotes: List[str]
@strawberry.type
class AgentResponse:
    answer: str
    matches: List[Tender]

def get_llm_completion(prompt: str, system_instruction: str = "You are a helpful assistant."):
    for model_cfg in MODEL_LIST:
        if not model_cfg["api_key"]: continue
        try:
            response = litellm.completion(
                model=model_cfg["model"],
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                api_key=model_cfg["api_key"],
                timeout=10
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Model {model_cfg['model']} failed. Moving to next...")
            continue
    raise Exception("All LLM providers exhausted or rate-limited.")

def get_qdrant_matches(query_text: str, limit: int = 5) -> List[Tender]:
    embedding_result = client_gemini_embed.models.embed_content(
        model="gemini-embedding-001",
        contents=query_text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
    )
    query_vector = embedding_result.embeddings[0].values
    search_results = client_qdrant.query_points(
        collection_name=COLLECTION_NAME, query=query_vector, limit=limit, with_payload=True
    ).points

    tenders = []
    for hit in search_results:
        pay = hit.payload

        tenders.append(Tender(
            title=pay.get("title") or pay.get("Title") or "Unknown Tender",
            contractingAuthority=pay.get("contractingAuthority") or pay.get("ContractingAuthority") or "",
            sector=pay.get("sector") or pay.get("Sector") or "",
            summary=pay.get("summary") or pay.get("Summary") or "",
            lat=float(pay.get("lat", 0.0)),
            lng=float(pay.get("lng", 0.0)),
            keywords=pay.get("keywords", []),
            qualityStatus=pay.get("quality_status", "unverified"),
            url=pay.get("URL") or pay.get("url"),
            referenceNumber=pay.get("referenceNumber") or pay.get("ReferenceNumber"),
            submissionDeadline=pay.get("submissionDeadline") or pay.get("SubmissionDeadline"),
            estimatedValue=pay.get("estimatedValue"),
            cpvCode=pay.get("cpvCode"),
            procedureType=pay.get("procedureType"),
            eligibilityCriteria=pay.get("eligibilityCriteria", []),
            fitTier=pay.get("fitTier"),
            fitReasons=[
                FitReason(
                    criterion=r.get("criterion", ""),
                    status=r.get("status", "unclear"),
                    reason=r.get("reason", "")
                )
                for r in pay.get("fitReasons", [])
            ],
            factsVerified=pay.get("factsVerified", True),
            factCheckNotes=pay.get("factCheckNotes", [])
        ))
    return tenders

@strawberry.type
class Query:
    @strawberry.field
    def search_tenders(self, query_text: str) -> List[Tender]:
        return get_qdrant_matches(query_text)

    @strawberry.field
    def ask_agent(self, question: str) -> AgentResponse:
        try:
            matched_tenders = get_qdrant_matches(question, limit=3)
        except Exception as e:
            print(f"Embedding error: {e}")
            matched_tenders = []

        try:
            analytical_triggers = ["how many", "count", "total", "average", "history"]
            is_analytical = any(t in question.lower() for t in analytical_triggers)

            if is_analytical:
                schema_info = """
                Table: historical_tenders
                Columns: title, sector, contractingAuthority, referenceNumber, url, quality_status
                Note: The 'sector' column contains strings like 'IT' or 'Construction', broad procurement categories.
                """
                sql_prompt = f"Given {schema_info}, write a SQLite query for: {question}. Output raw SQL only."
                sql_query = get_llm_completion(sql_prompt, "You are a SQL expert.")
                
                sql_query = sql_query.strip().replace("```sql", "").replace("```", "")
                
                with engine.connect() as conn:
                    db_res = conn.execute(text(sql_query)).fetchall()
                    summary_prompt = f"User asked: {question}. Data: {str(db_res)}. Summarize shortly."
                    answer_text = get_llm_completion(summary_prompt, "You are a data assistant.")
            else:
                context = "\n".join([f"- {t.title}: {t.summary}" for t in matched_tenders])
                prompt = f"Context:\n{context}\n\nQuestion: {question}"
                answer_text = get_llm_completion(prompt, "You are a sharp procurement analyst.")

        except Exception as e:
            print(f"CRITICAL AGENT ERROR: {traceback.format_exc()}")
            answer_text = "Sorry, at this moment my analytical brain is offline (all LLMs rate-limited), but I've pulled these tenders for you!"

        return AgentResponse(answer=answer_text, matches=matched_tenders)

schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)
app = FastAPI(title="TenderBot Intel")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(graphql_app, prefix="/graphql")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)