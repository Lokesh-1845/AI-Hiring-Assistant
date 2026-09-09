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

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

QDRANT_PATH = BASE_DIR / "qdrant_db"

COLLECTION_NAME = "chunked_data"

VECTOR_SIZE = 384

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# ============================================================
# 2. EMBEDDINGS
# ============================================================
# IMPORTANT:
# This is lazy-loaded.
#
# The model is NOT loaded when resume_intelligence_pro.py
# starts.
#
# It loads only when RAG is actually required.
# ============================================================

@st.cache_resource(
    show_spinner="Loading AI embedding model..."
)
def get_embeddings():

    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5"
    )


# ============================================================
# 3. QDRANT
# ============================================================
# Also lazy-loaded.
# ============================================================

@st.cache_resource
def get_qdrant_client():

    return QdrantClient(
        path=str(QDRANT_PATH)
    )


# ============================================================
# 4. VECTOR STORE
# ============================================================

@st.cache_resource
def get_vector_store():

    embeddings = get_embeddings()

    client = get_qdrant_client()

    if not client.collection_exists(
        COLLECTION_NAME
    ):

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
# 5. LLM
# ============================================================

@st.cache_resource
def get_llm():
    return ChatOpenAI(

        api_key=OPENROUTER_API_KEY,

        base_url="https://openrouter.ai/api/v1",

        model="google/gemini-2.5-flash",

        temperature=0,

        max_tokens=700
    )


# ============================================================
# 6. CREATE RESUME CHUNKS
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
# 7. INDEX RESUME
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
# 8. CANDIDATE FILTER
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
# 9. RETRIEVE RESUME CHUNKS
# ============================================================

def retrieve_resume_chunks(
    question,
    candidate_name,
    k=8
):

    vector_store = get_vector_store()

    candidate_filter = (
        create_candidate_filter(
            candidate_name
        )
    )

    documents = vector_store.similarity_search(

        query=question,

        k=k,

        filter=candidate_filter
    )

    return documents


# ============================================================
# 10. CREATE CONTEXT
# ============================================================

def create_context(
    documents
):

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
# 11. ASK RESUME QUESTION
# ============================================================

def ask_resume_question(
    question,
    candidate_name
):

    documents = retrieve_resume_chunks(

        question=question,

        candidate_name=candidate_name,

        k=8
    )

    if not documents:

        return (
            "I couldn't find relevant "
            "information in this candidate's resume."
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
# 12. BACKEND HEALTH CHECK
# ============================================================
# This does NOT load the HuggingFace model.
# It only tells the frontend whether the basic backend
# configuration is available.
#
# This function is intentionally NOT displayed in the UI.
# ============================================================

def check_rag_connection():
    """
    Lightweight RAG connection check.

    IMPORTANT:
    This function does NOT load the Hugging Face embedding model.
    Therefore it does not slow down Streamlit startup.
    """

    try:
        # Check Qdrant database folder
        if not QDRANT_PATH.exists():
            return {
                "connected": False,
                "qdrant": False,
                "embeddings": False,
                "message": "Qdrant database not found."
            }

        # Check API key configuration
        if not OPENROUTER_API_KEY:
            return {
                "connected": False,
                "qdrant": True,
                "embeddings": False,
                "message": "OpenRouter API key not configured."
            }

        # Try opening local Qdrant
        client = get_qdrant_client()

        if not client.collection_exists(
            COLLECTION_NAME
        ):
            return {
                "connected": False,
                "qdrant": True,
                "embeddings": False,
                "message": "RAG collection not found."
            }

        return {
            "connected": True,
            "qdrant": True,
            "embeddings": True,
            "message": "RAG backend is ready."
        }

    except Exception as e:

        return {
            "connected": False,
            "qdrant": False,
            "embeddings": False,
            "message": str(e)
        }


import os
from pathlib import Path
from dotenv import load_dotenv

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

# Explicitly specify the path to the .env file
env_path = Path(__file__).resolve().parent / ".env"

if not env_path.exists():
    print("Warning: .env file not found. Ensure the environment variables are set.")
else:
    try:
        load_dotenv(dotenv_path=env_path)
        print(".env file loaded successfully.")
    except Exception as e:
        print(f"Error loading .env file: {e}")

# Check if the API key is set
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set. Check your .env file.")

# ============================================================
# 13. DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    print(
        "rag_backend.py is a library module."
    )

    print(
        "Run resume_intelligence_pro.py instead."
    )
