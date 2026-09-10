
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from qdrant_client import QdrantClient, models

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_openai import ChatOpenAI


# ============================================================
# 1. ENVIRONMENT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# Load .env for LOCAL development
env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)


# ============================================================
# 2. OPENROUTER API KEY
# ============================================================
# Priority:
#
# 1. Streamlit Secrets
# 2. .env environment variable
#
# This allows the same code to work locally and on Streamlit Cloud.
# ============================================================

OPENROUTER_API_KEY = None

try:
    OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY")
except Exception:
    pass


if not OPENROUTER_API_KEY:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# ============================================================
# 3. PATHS / QDRANT CONFIGURATION
# ============================================================

QDRANT_PATH = BASE_DIR / "qdrant_db"

COLLECTION_NAME = "chunked_data"

VECTOR_SIZE = 384


# ============================================================
# 4. EMBEDDINGS
# ============================================================
# Lazy loaded.
#
# The Hugging Face model is NOT loaded when the application starts.
# It loads only when get_embeddings() is called.
# ============================================================

@st.cache_resource(show_spinner="Loading AI embedding model...")
def get_embeddings():

    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5"
    )


# ============================================================
# 5. QDRANT CLIENT
# ============================================================

@st.cache_resource
def get_qdrant_client():

    return QdrantClient(
        path=str(QDRANT_PATH)
    )


# ============================================================
# 6. VECTOR STORE
# ============================================================

@st.cache_resource
def get_vector_store():

    embeddings = get_embeddings()

    client = get_qdrant_client()

    if not client.collection_exists(COLLECTION_NAME):

        client.create_collection(

            collection_name=COLLECTION_NAME,

            vectors_config=models.VectorParams(

                size=VECTOR_SIZE,

                distance=models.Distance.COSINE
            )
        )

    return QdrantVectorStore(

        client=client,

        collection_name=COLLECTION_NAME,

        embedding=embeddings
    )


# ============================================================
# 7. LLM
# ============================================================

@st.cache_resource
def get_llm():

    if not OPENROUTER_API_KEY:

        raise ValueError(
            "OPENROUTER_API_KEY is not configured."
        )

    return ChatOpenAI(

        api_key=OPENROUTER_API_KEY,

        base_url="https://openrouter.ai/api/v1",

        model="google/gemini-2.5-flash",

        temperature=0,

        max_tokens=700
    )


# ============================================================
# 8. CREATE RESUME CHUNKS
# ============================================================

def create_resume_chunks(
    text,
    candidate_name,
    source
):

    splitter = RecursiveCharacterTextSplitter(

        chunk_size=500,

        chunk_overlap=50,

        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            ""
        ]
    )

    document = Document(

        page_content=text,

        metadata={
            "source": source,
            "candidate": candidate_name,
            "document_type": "resume"
        }
    )

    chunks = splitter.split_documents(
        [document]
    )

    for index, chunk in enumerate(chunks):

        chunk.metadata.update({

            "source": source,

            "candidate": candidate_name,

            "document_type": "resume",

            "chunk_id": index
        })

    return chunks


# ============================================================
# 9. INDEX RESUME
# ============================================================

def index_resume(
    text,
    candidate_name,
    source
):

    vector_store = get_vector_store()

    documents = create_resume_chunks(

        text=text,

        candidate_name=candidate_name,

        source=source
    )

    if not documents:

        return 0

    vector_store.add_documents(
        documents=documents
    )

    return len(documents)


# ============================================================
# 10. CANDIDATE FILTER
# ============================================================

def create_candidate_filter(
    candidate_name
):

    return models.Filter(

        must=[

            models.FieldCondition(

                key="metadata.candidate",

                match=models.MatchValue(
                    value=candidate_name
                )
            ),

            models.FieldCondition(

                key="metadata.document_type",

                match=models.MatchValue(
                    value="resume"
                )
            )
        ]
    )


# ============================================================
# 11. RETRIEVE RESUME CHUNKS
# ============================================================

def retrieve_resume_chunks(
    question,
    candidate_name,
    k=100
):

    vector_store = get_vector_store()

    candidate_filter = create_candidate_filter(
        candidate_name
    )

    documents = vector_store.similarity_search(

        query=question,

        k=k,

        filter=candidate_filter
    )

    return documents


# ============================================================
# 12. CREATE CONTEXT
# ============================================================

def create_context(documents):

    if not documents:

        return ""

    context_parts = []

    for document in documents:

        context_parts.append(
            document.page_content
        )

    return "\n\n".join(
        context_parts
    )


# ============================================================
# 13. ASK RESUME QUESTION
# ============================================================

def ask_resume_question(
    question,
    candidate_name
):

    documents = retrieve_resume_chunks(

        question=question,

        candidate_name=candidate_name,

        k=100
    )

    if not documents:

        return (
            "I couldn't find relevant information "
            "in this candidate's resume."
        )

    context = create_context(
        documents
    )

    prompt = f"""
You are an AI Hiring Assistant.

Answer the recruiter question ONLY
using the resume information below.

Candidate:
{candidate_name}

Resume Information:
{context}

Recruiter Question:
{question}

Rules:

1. Do not invent information.
2. Do not add skills that are not in the resume.
3. Do not add experience that is not in the resume.
4. Do not add projects that are not in the resume.
5. If the answer is not available, clearly say
   that the information is not available.
6. Give a clear and professional answer.
"""

    llm = get_llm()

    response = llm.invoke(
        prompt
    )

    return response.content


# ============================================================
# 14. RAG CONNECTION / HEALTH CHECK
# ============================================================
#
# IMPORTANT:
#
# This function is lightweight.
#
# It checks:
#   1. Qdrant database exists
#   2. OpenRouter API key exists
#   3. Qdrant client works
#   4. Required collection exists
#
# It DOES NOT load the Hugging Face embedding model.
#
# Therefore calling this function from the dashboard
# should NOT download/load the embedding model.
# ============================================================

def check_rag_connection():

    try:

        # ----------------------------------------------------
        # Check Qdrant database folder
        # ----------------------------------------------------

        if not QDRANT_PATH.exists():

            return {
                "connected": False,
                "qdrant": False,
                "embeddings": False,
                "openrouter": bool(OPENROUTER_API_KEY),
                "message": "Qdrant database folder not found."
            }


        # ----------------------------------------------------
        # Check OpenRouter API key
        # ----------------------------------------------------

        if not OPENROUTER_API_KEY:

            return {
                "connected": False,
                "qdrant": True,
                "embeddings": False,
                "openrouter": False,
                "message": "OpenRouter API key is not configured."
            }


        # ----------------------------------------------------
        # Test Qdrant
        # ----------------------------------------------------

        client = get_qdrant_client()


        # ----------------------------------------------------
        # Check collection
        # ----------------------------------------------------

        if not client.collection_exists(
            COLLECTION_NAME
        ):

            return {
                "connected": False,
                "qdrant": True,
                "embeddings": False,
                "openrouter": True,
                "message": (
                    f"Qdrant collection "
                    f"'{COLLECTION_NAME}' not found."
                )
            }


        # ----------------------------------------------------
        # Basic RAG configuration is ready
        # ----------------------------------------------------

        return {
            "connected": True,
            "qdrant": True,

            # This means embedding configuration is available,
            # NOT that the Hugging Face model was loaded.
            "embeddings": True,

            "openrouter": True,

            "message": "RAG backend is ready."
        }


    except Exception as e:

        return {
            "connected": False,
            "qdrant": False,
            "embeddings": False,
            "openrouter": False,
            "message": f"RAG connection error: {str(e)}"
        }


# ============================================================
# 15. DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    print(
        "rag_backend.py is a library module."
    )

    print(
        "Run resume_intelligence_pro.py instead."
    )