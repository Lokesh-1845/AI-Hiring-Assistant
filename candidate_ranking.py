from pathlib import Path

from ATS_score import (
    extract_required_terms,
    calculate_term_match,
    calculate_ats_score,
    get_score_category,
)

# ============================================================
# 1. PROJECT PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# 2. LOAD RESUMES
# ============================================================

resume_folder = BASE_DIR / "data" / "extracted_text"

resumes = {}

for file_path in resume_folder.glob("*.txt"):

    resume_text = file_path.read_text(
        encoding="utf-8"
    )

    if resume_text.strip():
        resumes[file_path.stem] = resume_text


# ============================================================
# 3. LOAD JOB DESCRIPTION
# ============================================================

jd_path = (
    BASE_DIR
    / "data"
    / "job_description"
    / "python_developer.txt"
)

jd_text = jd_path.read_text(
    encoding="utf-8"
)


# ============================================================
# 4. EXTRACT TERMS FROM JD
# ============================================================

required_terms = extract_required_terms(
    jd_text
)


# ============================================================
# 5. CANDIDATE RANKING
# ============================================================

ranked_candidates = []

for candidate_name, candidate_resume in resumes.items():

    matched_terms, missing_terms = calculate_term_match(
        required_terms,
        candidate_resume
    )

    ats_score = calculate_ats_score(
        required_terms,
        matched_terms
    )

    category = get_score_category(
        ats_score
    )

    ranked_candidates.append({
        "candidate": candidate_name,
        "ats_score": ats_score,
        "category": category,
        "matched_terms": matched_terms,
        "missing_terms": missing_terms
    })


# ============================================================
# 6. SORT BY ATS SCORE
# ============================================================

ranked_candidates.sort(
    key=lambda candidate: candidate["ats_score"],
    reverse=True
)


# ============================================================
# 7. DISPLAY RANKING
# ============================================================

print("\n" + "=" * 60)
print("CANDIDATE RANKING")
print("=" * 60)

for rank, candidate in enumerate(
    ranked_candidates,
    start=1
):

    print("\n" + "-" * 60)

    print(
        f"Rank: {rank}"
    )

    print(
        f"Candidate: {candidate['candidate']}"
    )

    print(
        f"ATS Score: {candidate['ats_score']}%"
    )

    print(
        f"Category: {candidate['category']}"
    )

    print(
        f"Matched Terms: "
        f"{', '.join(candidate['matched_terms'])}"
    )

    print(
        f"Missing Terms: "
        f"{', '.join(candidate['missing_terms'])}"
    )