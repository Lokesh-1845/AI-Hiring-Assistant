import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_openai import ChatOpenAI
import streamlit as st

OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set. Add it to Streamlit Secrets.")

llm = ChatOpenAI(api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",model="google/gemini-2.5-flash",temperature=0,max_tokens=512,)
# 3. INITIALIZE EMBEDDING MODEL
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
print("Embedding model loaded.")
# 4. CONNECT TO LOCAL QDRANT
qdrant_client = QdrantClient(path="./qdrant_db")
collection_name = "chunked_data"
print("Connected to local Qdrant.")
# 5. GET VECTOR SIZE
test_embedding = embeddings.embed_query("test")
vector_size = len(test_embedding)
print(f"Embedding vector size: {vector_size}")
# 6. CREATE COLLECTION IF IT DOES NOT EXIST
if not qdrant_client.collection_exists(collection_name):
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=vector_size,distance=models.Distance.COSINE))
    print(f"Collection '{collection_name}' created.")
else:
    print(f"Collection '{collection_name}' already exists.")
# 7. LOAD TXT RESUMES
def load_resumes(folder_path):
    folder = Path(folder_path)
    documents = []
    txt_files = list(folder.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {folder_path}")
    for file_path in txt_files:
        text = file_path.read_text(encoding="utf-8")
        if not text.strip():
            print(f"Skipping empty file: {file_path.name}")
            continue
        document = Document(
            page_content=text,
            metadata={"source": file_path.name,"candidate": file_path.stem})
        documents.append(document)
        print(f"Loaded resume: {file_path.name}")
    return documents
# ============================================================
# 8. CREATE CHUNKS
# ============================================================
def create_chunks(documents):
    splitter = RecursiveCharacterTextSplitter(chunk_size=500,chunk_overlap=50,separators=["\n\n","\n",". "," ",""])
    chunks = splitter.split_documents(documents)
    # Add chunk IDs
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = index
    return chunks
# ============================================================
# 9. LOAD RESUMES + CREATE CHUNKS
# ============================================================
documents = load_resumes("data/extracted_text")
print(f"\nTotal resumes loaded: {len(documents)}")
chunks = create_chunks(documents)
print(f"Total chunks created: {len(chunks)}")
# ============================================================
# 10. INITIALIZE QDRANT VECTOR STORE
# ============================================================
vector_store = QdrantVectorStore(client=qdrant_client,collection_name=collection_name,embedding=embeddings,)
print("Qdrant vector store initialized.")
# ============================================================
# 11. STORE CHUNKS + EMBEDDINGS IN QDRANT
# ============================================================
vector_store.add_documents(documents=chunks)
print("Resume chunks successfully stored in Qdrant.")
# ============================================================
# 12. CHECK DATA IN QDRANT
# ============================================================
try:
    points, next_offset = qdrant_client.scroll(collection_name=collection_name,limit=10,with_payload=True,with_vectors=False)
    if not points:
        print("\nNo data found in Qdrant.")
    else:
        print(f"\nFound {len(points)} records in Qdrant.")
        for point in points:
            print("\n" + "=" * 60)
            print(f"Point ID: {point.id}")
            print(f"Payload: {point.payload}")
except Exception as e:
    print(f"\nError checking Qdrant: {e}")
# ============================================================
# 13. CREATE RETRIEVER
# ============================================================
retriever = vector_store.as_retriever(search_kwargs={"k": 5})
# ============================================================
# 14. RAG FUNCTION
# ============================================================
def ask_question(question):
    # ----------------------------------------
    # Retrieve relevant resume chunks
    # ----------------------------------------
    documents = retriever.invoke(question)
    if not documents:
        return "No relevant resume information found."
    print("\nRetrieved Documents:")
    for doc in documents:
        print("\n" + "-" * 60)
        print("Source:",doc.metadata.get("source","Unknown"))
        print("Candidate:",doc.metadata.get("candidate","Unknown"))
        print("Chunk ID:",doc.metadata.get("chunk_id","Unknown"))
        print("Content:",doc.page_content)
    # ----------------------------------------
    # Build context
    # ----------------------------------------
    context_parts = []
    for doc in documents:
        context_parts.append(f"""Candidate:{doc.metadata.get("candidate", "Unknown")} 
                             Source:{doc.metadata.get("source", "Unknown")}
                             Resume Content:{doc.page_content}""")

    context = "\n\n".join(context_parts)
    # ----------------------------------------
    # Build prompt
    # ----------------------------------------
    prompt = f"""
You are an AI Hiring Assistant.

Answer the recruiter question ONLY using
the resume information provided below.

Do not invent skills, experience,
education, or technologies.

If something is not available in the resumes,
clearly say that the information is unavailable.

Resume Information:
{context}

Recruiter Question:
{question}

Give a clear and professional answer.
"""
    # ----------------------------------------
    # Call LLM
    # ----------------------------------------
    response = llm.invoke(prompt)
    return response.content
# ============================================================
# 15. MAIN PROGRAM
# ============================================================
if __name__ == "__main__":
    print("\n")
    print("=" * 60)
    print("AI HIRING ASSISTANT")
    print("=" * 60)
    while True:
        question = input("\nEnter recruiter question ""(or type 'exit'): ")
        if question.lower().strip() == "exit":
            print("\nExiting...")
            break
        try:
            answer = ask_question(question)
            print("\nAnswer:")
            print(answer)
        except Exception as e:
            print("\nError:")
            print(e)
    qdrant_client.close()
    print("\nQdrant client closed.")







'''

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from langchain_qdrant import QdrantVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
import os

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()
import os

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set. Check your .env file.")

import streamlit as st

OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
# ============================================================
# INITIALIZE OPENAI-COMPATIBLE LLM
# ============================================================

llm = ChatOpenAI(
    api_key="OPENROUTER_API_KEY",
    base_url="https://openrouter.ai/api/v1",
    model="google/gemini-2.5-flash",
    temperature=0,
    max_tokens=512,
)

# ============================================================
# INITIALIZE EMBEDDING MODEL
# ============================================================

embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)

# ============================================================
# CONNECT TO LOCAL QDRANT
# ============================================================

qdrant_client = QdrantClient(
    path="./qdrant_db"
)

collection_name = "chunked_data"

# ============================================================
# GET EMBEDDING VECTOR SIZE
# ============================================================

test_embedding = embeddings.embed_query("test")
vector_size = len(test_embedding)
print(f"Embedding vector size: {vector_size}")

# ============================================================
# CHECK IF COLLECTION EXISTS
# ============================================================

try:
    qdrant_client.get_collection(collection_name=collection_name)
    print(f"Collection '{collection_name}' already exists.")
except Exception:
    print(f"Collection '{collection_name}' not found. Creating collection...")
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE
        )
    )
    print(f"Collection '{collection_name}' created successfully.")

# ============================================================
# INITIALIZE VECTOR STORE
# ============================================================

vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=collection_name,
    embedding=embeddings,
)

print("Qdrant vector store initialized successfully.")

# ============================================================
# RETRIEVE AND INSPECT DATA FROM QDRANT
# ============================================================

try:
    results = qdrant_client.scroll(
        collection_name=collection_name,
        limit=10  # Retrieve the first 10 vectors
    )
    if results is None or len(results[0]) == 0:
        print("\nNo data found in the Qdrant collection.")
    else:
        print("\nData in Qdrant:")
        for vector, payload in zip(results[0], results[1]):
            print(f"Vector: {vector[:10]}...")  # Print the first 10 values for brevity
            print(f"Metadata: {payload}")
            print("------------------------------------------")
except Exception as e:
    print(f"\nError retrieving data from Qdrant: {e}")

# ============================================================
# CREATE RETRIEVER
# ============================================================

retriever = vector_store.as_retriever(search_kwargs={"k": 5})

# ============================================================
# RAG FUNCTION
# ============================================================

def ask_question(question):
    """
    Search the resume database and answer a recruiter question.
    """

    # Step 1: Retrieve relevant resume chunks
    documents = retriever.invoke(question)

    # Debug: Print retrieved documents with metadata
    print("\nRetrieved Documents:")
    for doc in documents:
        print(f"Source: {doc.metadata.get('source', 'Unknown')}")
        print(f"Candidate: {doc.metadata.get('candidate', 'Unknown')}")
        print(f"Chunk ID: {doc.metadata.get('chunk_id', 'Unknown')}")
        print(f"Content: {doc.page_content}")
        print("------------------------------------------")

    # Step 2: Build context
    context = ""
    for doc in documents:
        context += f"""
Candidate: {doc.metadata.get('candidate', 'Unknown')}
Source: {doc.metadata.get('source', 'Unknown')}
Chunk ID: {doc.metadata.get('chunk_id', 'Unknown')}

Resume Content:
{doc.page_content}

------------------------------------------
"""

    # Step 3: Build Prompt
    prompt = f"""
You are an AI Hiring Assistant.

Answer ONLY from the retrieved resumes.

Never invent skills.

If information is missing,
clearly mention what information is unavailable,
but still compare the available facts.

Resume Information:
{context}

Recruiter Question:
{question}

Provide a clear and professional answer.
"""

    # Step 4: Call OpenRouter
    response = llm.invoke(prompt)
    return response.content

# ============================================================
# SIMPLE ANSWER FUNCTION
# ============================================================

def answer(question):
    """
    Public function used by the application.
    """
    return ask_question(question)

# ============================================================
# TEST PROGRAM
# ============================================================

if __name__ == "__main__":
    print("\nAI Hiring Assistant")
    print("-------------------")

    while True:
        # Prompt the user for a question
        question = input("\nEnter your recruiter question (or type 'exit' to quit): ")

        # Check if the user wants to exit
        if question.lower() == "exit":
            print("\nExiting AI Hiring Assistant...")
            break

        try:
            # Get the answer to the question
            result = answer(question)
            print("\nAnswer:")
            print(result)
        except Exception as e:
            print("\nError:")
            print(e)

    # Close the Qdrant client explicitly
    qdrant_client.close()
    print("\nQdrant client closed successfully.")'''