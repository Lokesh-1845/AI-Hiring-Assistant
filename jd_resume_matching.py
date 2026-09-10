import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_openai import ChatOpenAI

from ATS_score import (
    extract_required_terms,
    calculate_term_match,
    calculate_ats_score,
    get_score_category,
)


# --------------------------------------------------
# 1. Load environment variables
# --------------------------------------------------

import streamlit as st

OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set. Add it to Streamlit Secrets.")
# --------------------------------------------------
# 2. Base directory
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


# --------------------------------------------------
# 3. Load Job Description
# --------------------------------------------------

jd_path = (
    BASE_DIR
    / "data"
    / "job_description"
    / "python_developer.txt"
)

if not jd_path.exists():
    raise FileNotFoundError(
        f"Job description not found: {jd_path}"
    )

jd_text = jd_path.read_text(
    encoding="utf-8"
)

print("\nJob Description loaded successfully.")


# --------------------------------------------------
# 4. Load resumes
# --------------------------------------------------

resume_folder = (
    BASE_DIR
    / "data"
    / "extracted_text"
)

if not resume_folder.exists():
    raise FileNotFoundError(
        f"Resume folder not found: {resume_folder}"
    )

resumes = {}

for file_path in resume_folder.glob("*.txt"):

    resume_text = file_path.read_text(
        encoding="utf-8"
    )

    if resume_text.strip():

        resumes[file_path.stem] = resume_text

        print(
            f"Loaded resume: {file_path.name}"
        )


if not resumes:
    raise ValueError(
        "No resume .txt files were found."
    )


# --------------------------------------------------
# 5. Extract JD requirements
# --------------------------------------------------

required_terms = extract_required_terms(
    jd_text
)

print("\nRequired JD Terms:")
print("=" * 60)

for term in required_terms:
    print(term)


# --------------------------------------------------
# 6. Create embeddings
# --------------------------------------------------

embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)


# --------------------------------------------------
# 7. Connect to Qdrant
# --------------------------------------------------

qdrant_client = QdrantClient(
    path=str(BASE_DIR / "qdrant_db")
)

collection_name = "chunked_data"

vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=collection_name,
    embedding=embeddings,
)


# --------------------------------------------------
# 8. Create LLM
# --------------------------------------------------

llm = ChatOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model="google/gemini-2.5-flash",
    temperature=0,
    max_tokens=700,
)


# --------------------------------------------------
# 9. Candidate filter
# --------------------------------------------------

def create_candidate_filter(candidate_name):

    return models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.candidate",
                match=models.MatchValue(
                    value=candidate_name
                )
            )
        ]
    )


# --------------------------------------------------
# 10. Retrieve relevant resume chunks
# --------------------------------------------------

def retrieve_resume_chunks(
    candidate_name,
    job_description
):

    candidate_filter = create_candidate_filter(
        candidate_name
    )

    documents = vector_store.similarity_search(
        query=job_description,
        k=10,
        filter=candidate_filter
    )

    return documents


# --------------------------------------------------
# 11. Create resume context
# --------------------------------------------------

def create_context(documents):

    if not documents:
        return ""

    context_parts = []

    for doc in documents:

        context_parts.append(
            doc.page_content
        )

    return "\n\n".join(
        context_parts
    )


# --------------------------------------------------
# 12. Create matching prompt
# --------------------------------------------------

def create_matching_prompt(
    candidate_name,
    job_description,
    ats_score,
    category,
    matched_terms,
    missing_terms,
    context
):

    prompt = f"""
You are an AI Hiring Assistant.

Analyze how well the candidate matches the
provided Job Description.

Candidate:
{candidate_name}

ATS Match Score:
{ats_score}%

Match Category:
{category}

Matched JD Terms:
{", ".join(matched_terms)}

Missing JD Terms:
{", ".join(missing_terms)}

Job Description:
{job_description}

Relevant Resume Information:
{context}

IMPORTANT RULES:

1. Use ONLY the provided resume information.

2. Do NOT invent skills, experience, projects,
   companies, education, certifications,
   technologies, or achievements.

3. Do not assume that a missing term means the
   candidate definitely does not have that skill.
   Say that it is not clearly mentioned in the resume.

4. Explain why the matched skills are relevant
   to the Job Description.

5. Identify weak or missing areas.

6. Do not change the ATS score.

7. Do not calculate a different score.

8. Give a practical hiring recommendation.

Use this format:

Candidate: {candidate_name}

Match Score: {ats_score}%

Strong Matches:
- <skill and evidence>

Relevant Experience:
- <resume evidence relevant to the JD>

Missing / Weak Areas:
- <missing or unclear requirement>

Recommendation:
<short hiring recommendation>

Do not show retrieved chunks.
Do not mention RAG.
Do not mention Qdrant.
Do not mention the context.

Give a concise professional answer.
"""

    return prompt


# --------------------------------------------------
# 13. Match one candidate
# --------------------------------------------------

def match_candidate(
    candidate_name,
    candidate_resume
):

    # ATS matching

    matched_terms, missing_terms = (
        calculate_term_match(
            required_terms,
            candidate_resume
        )
    )

    ats_score = calculate_ats_score(
        required_terms,
        matched_terms
    )

    category = get_score_category(
        ats_score
    )

    # RAG retrieval

    documents = retrieve_resume_chunks(
        candidate_name,
        jd_text
    )

    context = create_context(
        documents
    )

    if not context:

        context = (
            "No relevant resume information "
            "was retrieved."
        )

    # LLM prompt

    prompt = create_matching_prompt(
        candidate_name,
        jd_text,
        ats_score,
        category,
        matched_terms,
        missing_terms,
        context
    )

    response = llm.invoke(
        prompt
    )

    return response.content


# --------------------------------------------------
# 14. Run matching for all candidates
# --------------------------------------------------

print("\n" + "=" * 60)
print("JD + RESUME MATCHING")
print("=" * 60)

try:

    for candidate_name, candidate_resume in resumes.items():

        print("\n" + "-" * 60)

        print(
            f"Candidate: {candidate_name}"
        )

        print("-" * 60)

        result = match_candidate(
            candidate_name,
            candidate_resume
        )

        print("\nAI Match Analysis:")
        print(result)

finally:

    qdrant_client.close()