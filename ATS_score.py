from pathlib import Path
import re
# 1. PROJECT PATH
BASE_DIR = Path(__file__).resolve().parent
# 2. LOAD RESUMES
resume_folder = BASE_DIR / "data" / "extracted_text"
resumes = {}
if not resume_folder.exists():
    raise FileNotFoundError(f"Resume folder not found: {resume_folder}")
for file_path in resume_folder.glob("*.txt"):
    resume_text = file_path.read_text(encoding="utf-8")
    if resume_text.strip():
        resumes[file_path.stem] = resume_text
        print(f"Loaded resume: {file_path.name}")
if not resumes:
    raise ValueError("No resume .txt files were found.")
# ============================================================
# 3. LOAD JOB DESCRIPTION
# ============================================================
jd_path = (BASE_DIR/ "data"/ "job_description"/"python_developer.txt")
if not jd_path.exists():
    raise FileNotFoundError(f"Job description not found: {jd_path}")
jd_text = jd_path.read_text(encoding="utf-8")
print("\nJob Description loaded successfully.")
# ============================================================
# 4. NORMALIZE TEXT
# ============================================================
def normalize_text(text):
    # Convert text to lowercase and remove unnecessary spaces.
    text = text.lower()
    text = re.sub(r"\s+"," ",text)
    return text.strip()
# ============================================================
# 5. EXTRACT IMPORTANT TERMS FROM JOB DESCRIPTION
# ============================================================
def extract_required_terms(job_description):
    #Extract words/terms from the job description. This avoids manually entering a fixed skill list.
    job_description = normalize_text(job_description)
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.-]*\b",job_description)
    # Remove common English words that are not useful
    # for ATS matching.
    stop_words = {
        "and","the","for","with","from","that","this","will","have","has","are","you","your","our","job","role","work","working",
        "experience","years","year","using","use","ability","required","requirements","candidate","team","strong","good",
        "knowledge", "skills","responsibilities"}
    required_terms = []
    for word in words:
        if (
            len(word) > 2 and word not in stop_words and word not in required_terms):
            required_terms.append(word)
    return required_terms
# ============================================================
# 6. CHECK WHETHER A TERM EXISTS IN RESUME
# ============================================================
def term_exists(term, resume_text):
    #Check whether a required term appears in the resume.
    term = normalize_text(term)
    resume_text = normalize_text(resume_text)
    return term in resume_text
# ============================================================
# 7. CALCULATE MATCHED AND MISSING TERMS
# ============================================================
def calculate_term_match(required_terms,resume_text):
    #Compare job description terms against resume text.
    matched_terms = []
    missing_terms = []
    for term in required_terms:
        if term_exists(term, resume_text):
            matched_terms.append(term)
        else:
            missing_terms.append(term)
    return matched_terms, missing_terms
# ============================================================
# 8. CALCULATE ATS SCORE
# ============================================================
def calculate_ats_score(required_terms,matched_terms):
    #Calculate ATS score as a percentage.
    if not required_terms:
        return 0
    score = (len(matched_terms)/len(required_terms)) * 100
    return round(score, 2)
# ============================================================
# 9. GET SCORE CATEGORY
# ============================================================
def get_score_category(score):
    if score >= 80:
        return "Strong Match"
    elif score >= 60:
        return "Moderate Match"
    elif score >= 40:
        return "Weak Match"
    else:
        return "Poor Match"
# ============================================================
# 10. EXTRACT TERMS FROM ORIGINAL JOB DESCRIPTION
# ============================================================
required_terms = extract_required_terms(jd_text)
print("\nTerms extracted from Job Description:")
print("=" * 60)
for term in required_terms:
    print(term)
# ============================================================
# 11. SCORE ALL ORIGINAL RESUMES
# ============================================================
print("\n" + "=" * 60)
print("ATS RESULTS")
print("=" * 60)
for candidate_name, candidate_resume in resumes.items():
    matched_terms, missing_terms = (
        calculate_term_match(required_terms,candidate_resume))
    ats_score = calculate_ats_score(required_terms,matched_terms)
    category = get_score_category(ats_score)
    print("\n" + "-" * 60)
    print(f"Candidate: {candidate_name}")
    print("-" * 60)
    print(f"ATS Score: {ats_score}%")
    print(f"Category: {category}")
    print("\nMatched Terms:")
    if matched_terms:
        for term in matched_terms:
            print(f"✓ {term}")
    else:
        print("None")
    print("\nMissing Terms:")
    if missing_terms:
        for term in missing_terms:
            print(f"✗ {term}")
    else:
        print("None")
        