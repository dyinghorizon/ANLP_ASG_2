from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Julius Caesar Expert Scholar API",
    description="RAG-powered API for Shakespeare's Julius Caesar",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The question about Julius Caesar")
    top_k: int = Field(default=5, ge=1, le=10, description="Number of relevant chunks to retrieve")
    include_sources: bool = Field(default=True, description="Whether to include source citations")


class SourceChunk(BaseModel):
    chunk_id: str
    text: str
    act: int
    scene: int
    chunk_type: str
    speaker: Optional[str] = None
    similarity: float


class QueryResponse(BaseModel):
    answer: str
    sources: Optional[List[SourceChunk]] = None
    metadata: Dict = {}


class RAGSystem:
    def __init__(self):
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None
        self.llm = None

    def initialize(self):
        logger.info("Initializing RAG System...")

        logger.info("Loading embedding model...")
        self.embedding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")
        logger.info("Embedding model loaded")

        logger.info("Connecting to ChromaDB...")
        self.chroma_client = chromadb.PersistentClient(
            path="db",
            settings=Settings(anonymized_telemetry=False)
        )

        try:
            self.collection = self.chroma_client.get_collection(name="julius_caesar")
            count = self.collection.count()
            logger.info(f"Connected to collection with {count} chunks")
        except Exception as e:
            logger.error(f"Failed to get collection: {e}")
            raise

        logger.info("Initializing Gemini LLM...")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite",
            temperature=0.2,
            max_tokens=2048
        )
        logger.info("Gemini LLM initialized")

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        try:
            query_embedding = self.embedding_model.encode(
                [query],
                normalize_embeddings=True
            )[0].tolist()

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=['documents', 'metadatas', 'distances']
            )

            retrieved_chunks = []
            for i in range(len(results['ids'][0])):
                chunk = {
                    'chunk_id': results['ids'][0][i],
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i],
                    'similarity': 1 - results['distances'][0][i]
                }
                retrieved_chunks.append(chunk)

            return retrieved_chunks

        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            raise

    def generate_answer(self, query: str, context_chunks: List[Dict]) -> str:
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            metadata = chunk['metadata']
            act = metadata.get('act', '?')
            scene = metadata.get('scene', '?')
            chunk_type = metadata.get('chunk_type', 'unknown')
            speaker = metadata.get('speaker', '')

            context_header = f"[Source {i} - Act {act}, Scene {scene}, Type: {chunk_type}"
            if speaker:
                context_header += f", Speaker: {speaker}"
            context_header += "]"

            context_parts.append(f"{context_header}\n{chunk['text']}\n")

        full_context = "\n".join(context_parts)

        system_prompt = """You are an Expert Shakespearean Scholar specializing in "The Tragedy of Julius Caesar."

**Your Role:**
- You are tutoring an ICSE Class 10 student
- Your answers must be academically rigorous yet clear and accessible
- You MUST ALWAYS cite textual evidence from the provided sources
- You explain complex themes, character motivations, and literary devices

**Critical Rules:**
1. ONLY use information from the provided context sources
2. ALWAYS cite which Act and Scene your evidence comes from (e.g., "In Act 3, Scene 2...")
3. If the context doesn't contain enough information, say so clearly
4. Be insightful - don't just summarize, analyze and interpret
5. For character questions, discuss motivations, conflicts, and development
6. For thematic questions, provide examples and explain significance
7. Keep your tone scholarly but approachable for a Class 10 student

**Response Format:**
- Start with a clear, direct answer
- Support with specific textual evidence (with citations)
- For complex questions, break down into key points
- End with insight or significance when appropriate"""

        user_prompt = f"""**Context from Julius Caesar:**

{full_context}

**Student's Question:**
{query}

**Your Answer (as an Expert Shakespearean Scholar):**"""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = self.llm.invoke(user_prompt)
            answer = response.content.strip()

            return answer

        except Exception as e:
            logger.error(f"Generation error: {e}")
            raise

rag_system = RAGSystem()

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Julius Caesar RAG API...")
    try:
        rag_system.initialize()
        logger.info("RAG System ready!")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Julius Caesar RAG API...")

@app.get("/")
async def root():
    return {
        "message": "Julius Caesar Expert Scholar API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "query": "/query (POST)",
            "health": "/health (GET)",
            "stats": "/stats (GET)"
        }
    }

@app.get("/health")
async def health_check():
    try:
        count = rag_system.collection.count()
        return {
            "status": "healthy",
            "collection_size": count,
            "embedding_model": "BAAI/bge-base-en-v1.5",
            "llm_model": "gemini-2.0-flash-exp"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"System unhealthy: {str(e)}")

@app.get("/stats")
async def get_stats():
    try:
        all_data = rag_system.collection.get(include=['metadatas'])
        metadatas = all_data['metadatas']

        stats = {
            'total_chunks': len(metadatas),
            'scene_chunks': sum(1 for m in metadatas if m.get('chunk_type') == 'scene'),
            'soliloquy_chunks': sum(1 for m in metadatas if m.get('chunk_type') == 'soliloquy'),
            'acts_covered': sorted(set(m.get('act', 0) for m in metadatas if m.get('act'))),
            'unique_scenes': len(set((m.get('act', 0), m.get('scene', 0))
                                     for m in metadatas if m.get('act') and m.get('scene')))
        }

        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    try:
        logger.info(f"Processing query: {request.query[:100]}...")

        logger.info(f"Retrieving top {request.top_k} chunks...")
        retrieved_chunks = rag_system.retrieve(request.query, top_k=request.top_k)

        if not retrieved_chunks:
            raise HTTPException(
                status_code=404,
                detail="No relevant information found in the play"
            )

        logger.info("Generating expert answer...")
        answer = rag_system.generate_answer(request.query, retrieved_chunks)

        sources = None
        if request.include_sources:
            sources = [
                SourceChunk(
                    chunk_id=chunk['chunk_id'],
                    text=chunk['text'][:500] + "..." if len(chunk['text']) > 500 else chunk['text'],
                    act=int(chunk['metadata'].get('act', 0)),
                    scene=int(chunk['metadata'].get('scene', 0)),
                    chunk_type=chunk['metadata'].get('chunk_type', 'unknown'),
                    speaker=chunk['metadata'].get('speaker'),
                    similarity=round(chunk['similarity'], 3)
                )
                for chunk in retrieved_chunks
            ]

        response = QueryResponse(
            answer=answer,
            sources=sources,
            metadata={
                'num_sources_used': len(retrieved_chunks),
                'query_length': len(request.query)
            }
        )

        logger.info("Response generated successfully")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)