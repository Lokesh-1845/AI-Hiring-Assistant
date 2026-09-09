import os
from pathlib import Path

from dotenv import load_dotenv

from qdrant_client import QdrantClient, models

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_openai import ChatOpenAI


# ============================================================
# 1. LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

import os

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set. Check your .env file.")

import streamlit as st

OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
# ============================================================
# 2. PROJECT PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# 3. RESUME FOLDER
# ============================================================

resume_folder = (
    BASE_DIR
    / "data"
    / "extracted_text"
)


# ============================================================
# 4. LOAD CANDIDATE NAMES
# ============================================================

if not resume_folder.exists():
    raise FileNotFoundError(
        f"Resume folder not found: {resume_folder}"
    )


candidates = []

for file_path in resume_folder.glob("*.txt"):

    resume_text = file_path.read_text(
        encoding="utf-8"
    )

    if resume_text.strip():

        candidates.append(
            file_path.stem
        )


if not candidates:
    raise ValueError(
        "No resume .txt files were found."
    )


# ============================================================
# 5. HUGGING FACE EMBEDDINGS
# ============================================================

embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)


# ============================================================
# 6. QDRANT CONNECTION
# ============================================================

qdrant_client = QdrantClient(
    path=str(BASE_DIR / "qdrant_db")
)

collection_name = "chunked_data"


# ============================================================
# 7. CONNECT LANGCHAIN TO QDRANT
# ============================================================

vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=collection_name,
    embedding=embeddings,
)


# ============================================================
# 8. OPENROUTER LLM
# ============================================================

llm = ChatOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model="google/gemini-2.5-flash",
    temperature=0,
    max_tokens=512,
)


# ============================================================
# 9. DISPLAY CANDIDATES
# ============================================================

def display_candidates():

    print("\n" + "=" * 60)
    print("AVAILABLE CANDIDATES")
    print("=" * 60)

    for index, candidate in enumerate(
        candidates,
        start=1
    ):

        print(
            f"{index}. {candidate}"
        )


# ============================================================
# 10. SELECT CANDIDATE
# ============================================================

def select_candidate():

    display_candidates()

    while True:

        try:

            choice = int(
                input(
                    "\nSelect candidate number: "
                )
            )

            if 1 <= choice <= len(candidates):

                selected_candidate = candidates[
                    choice - 1
                ]

                print(
                    f"\nSelected candidate: "
                    f"{selected_candidate}"
                )

                return selected_candidate

            else:

                print(
                    "Invalid candidate number."
                )

        except ValueError:

            print(
                "Please enter a valid number."
            )


# ============================================================
# 11. CREATE CANDIDATE FILTER
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
            )
        ]
    )


# ============================================================
# 12. RETRIEVE RESUME CHUNKS
# ============================================================

def retrieve_resume_chunks(
    question,
    candidate_name
):

    candidate_filter = create_candidate_filter(
        candidate_name
    )

    documents = vector_store.similarity_search(
        query=question,
        k=50,
        filter=candidate_filter
    )

    return documents


# ============================================================
# 13. CREATE RESUME CONTEXT
# ============================================================

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


# ============================================================
# 14. CHECK WHETHER USER IS ASKING FOR SUGGESTIONS
# ============================================================

def is_suggestion_question(question):

    suggestion_words = [
        "suggest",
        "suggestion",
        "suggestions",
        "improve",
        "improvement",
        "improvements",
        "recommend",
        "recommendation",
        "recommendations",
        "advice",
        "better",
        "enhance",
        "enhancement",
        "how can i improve",
        "what should i improve",
        "what can i improve",
        "what should be changed",
        "what can be changed"
    ]

    question = question.lower()

    for word in suggestion_words:

        if word in question:
            return True

    return False


# ============================================================
# 15. CREATE NORMAL QUESTION PROMPT
# ============================================================

def create_question_prompt(
    question,
    candidate_name,
    context
):

    prompt = f"""
You are an AI Resume Assistant.

You are answering a recruiter question about
one specific candidate.

Candidate:
{candidate_name}

Use ONLY the resume information provided below.

Do not invent:
- skills
- experience
- projects
- education
- companies
- job titles
- technologies
- years of experience

If the recruiter asks about projects:

Identify ALL projects available in the resume
context.

For each project use:

Project Name: <project name>
Description: <short description>

Do not show the retrieved resume chunks.

Do not mention the RAG system.

Do not mention the context.

If the requested information is not available,
say:

"The information is not available in this resume."

Resume Context:
{context}

Recruiter's Question:
{question}

Give a clear and concise professional answer.
"""

    return prompt


# ============================================================
# 16. CREATE SUGGESTION PROMPT
# ============================================================

def create_suggestion_prompt(
    question,
    candidate_name,
    context
):

    prompt = f"""
You are an AI Resume Improvement Assistant.

You are helping a recruiter review one specific
candidate's resume.

Candidate:
{candidate_name}

The resume information is provided below.

Your task is to provide useful suggestions for
improving the resume.

IMPORTANT RULES:

1. Base your observations on the actual resume
   information provided.

2. Do NOT invent skills, projects, companies,
   education, certifications, or experience.

3. Do NOT claim that the candidate has a skill
   that is not present in the resume.

4. You may suggest how existing information
   could be presented more clearly.

5. You may suggest adding measurable achievements
   if the candidate has those achievements but
   they are not currently quantified.

6. Do not create fake numbers or achievements.

7. Keep suggestions practical and useful for a
   recruiter or candidate.

8. If something is missing, say that it appears
   to be missing from the resume rather than
   assuming the candidate does not have it.

Provide suggestions in this format:

Resume Suggestions:

1. <suggestion>
   Reason: <why this would improve the resume>

2. <suggestion>
   Reason: <why this would improve the resume>

3. <suggestion>
   Reason: <why this would improve the resume>

Focus on areas such as:
- project descriptions
- skills presentation
- work experience
- achievements
- education
- certifications
- clarity
- measurable impact
- technical details
- resume structure

Do NOT show the retrieved resume chunks.

Do NOT mention the RAG system.

Do NOT mention the context.

Resume Information:
{context}

Recruiter's Request:
{question}

Give concise and actionable suggestions.
"""

    return prompt


# ============================================================
# 17. ASK QUESTION / GIVE SUGGESTION
# ============================================================

def ask_question(
    question,
    candidate_name
):

    documents = retrieve_resume_chunks(
        question,
        candidate_name
    )

    if not documents:

        return (
            "The requested information is not "
            "available in this resume."
        )


    context = create_context(
        documents
    )


    # ========================================================
    # DETERMINE QUESTION TYPE
    # ========================================================

    if is_suggestion_question(question):

        prompt = create_suggestion_prompt(
            question,
            candidate_name,
            context
        )

    else:

        prompt = create_question_prompt(
            question,
            candidate_name,
            context
        )


    # ========================================================
    # CALL LLM
    # ========================================================

    response = llm.invoke(
        prompt
    )

    return response.content


# ============================================================
# 18. RESUME CHAT
# ============================================================

def resume_chat():

    selected_candidate = select_candidate()


    print("\n" + "=" * 60)
    print("RESUME CHAT + RESUME SUGGESTIONS")
    print("=" * 60)

    print(
        f"Candidate: {selected_candidate}"
    )

    print(
        "\nAsk questions about the resume or "
        "request suggestions."
    )

    print(
        "Type 'exit' to end the chat."
    )


    while True:

        question = input(
            "\nRecruiter: "
        ).strip()


        # ----------------------------------------------------
        # EXIT
        # ----------------------------------------------------

        if question.lower() == "exit":

            print(
                "\nResume chat ended."
            )

            break


        # ----------------------------------------------------
        # EMPTY QUESTION
        # ----------------------------------------------------

        if not question:

            print(
                "Please enter a question."
            )

            continue


        # ----------------------------------------------------
        # GET ANSWER
        # ----------------------------------------------------

        try:

            answer = ask_question(
                question,
                selected_candidate
            )

            print(
                "\nAI Resume Assistant:"
            )

            print(
                answer
            )

        except Exception as error:

            print(
                "\nError:"
            )

            print(
                error
            )


# ============================================================
# 19. MAIN
# ============================================================

if __name__ == "__main__":

    try:

        resume_chat()

    finally:

        qdrant_client.close()