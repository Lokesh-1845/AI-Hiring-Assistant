'''"""Claude finished the response
Thought for 10s

That's very likely a stale session state problem, not a bug in the extraction logic itself. Here's why: Streamlit keeps your st.session_state alive across app restarts in the same browser tab/session. If you ever ran the old mock version in that same browser tab, your candidate names are still cached with the old fake data — and the code was written to skip re-parsing if a candidate with that name already exists. So new uploads with the same filename silently reuse old fake entries.

Let me fix that, plus add real diagnostics so you can see exactly what got extracted from your file (useful if it's a scanned/image PDF, which pypdf can't read at all).
Ran 10 commands, edited 8 files, and 8 more tools

What was actually wrong, and what I fixed:

    Stale session cache (the main culprit) — candidates were keyed only by filename. If you'd ever run an older/mock version of the app in that same browser tab, or re-uploaded a file with the same name, the app reused the old cached entry instead of re-parsing your new file. Fix: candidates are now keyed by name + content hash, so any new or edited file is always freshly parsed from scratch.
    No way to reset — I added a "🗑️ Clear All Candidates" button on the Upload page so you can wipe stale session data in one click.
    Silent failure on scanned PDFs — if your resume PDF is an image/scan with no real text layer, pypdf extracts nothing, and the old version would show an empty-but-not-obviously-wrong preview. Now:
        Added a pdfplumber fallback extractor for PDFs pypdf struggles with.
        If extraction still yields no usable text, you'll see a clear on-screen warning: "No readable text could be extracted... likely a scanned image PDF."
    Verify-it-yourself panel — every candidate card now has a "View raw extracted text" expander showing exactly what was pulled from your file, so you can confirm it matches your actual resume before trusting the skills/ATS output.

To fix it on your end right now:
bash

pip install streamlit pandas plotly pypdf python-docx pdfplumber
streamlit run resume_intelligence_pro.py

Then in the app: go to Upload Resume → click "Clear All Candidates" first (to flush any old cached data), then re-upload your file. Open the "View raw extracted text" expander to confirm the text matches your actual resume — if it comes back empty, your PDF is likely scanned/image-based and needs a text-based export instead.
Resume intelligence pro
PY 

import pdfplumber how toinstall this

Install it with pip:
bash

pip install pdfplumber

If that doesn't work, try one of these depending on your setup:
bash

pip3 install pdfplumber

bash

python -m pip install pdfplumber

bash

python3 -m pip install pdfplumber

Since your app needs several packages together, you can install them all at once:
bash

pip install streamlit pandas plotly pypdf python-docx pdfplumber

If you're using a virtual environment, activate it first:
bash

# Windows
venv\Scripts\activate
pip install pdfplumber

# macOS/Linux
source venv/bin/activate
pip install pdfplumber

After installing, import pdfplumber will work, and you can run the app:
bash

streamlit run resume_intelligence_pro.py

from pathlib import Path import re # 1. PROJECT PATH BASE_DIR = Path(__file__).resolve().parent # 2. LOAD RESUMES resume_folder = BASE_DIR / "data" / "extracted_text" resumes = {} if not resume_folder.exists():     raise FileNotFoundError(f"Resume folder not found: {resume_folder}") for file_path in

pasted
Thought for 11s

Got it — I'll integrate both pieces from your scripts:

    Dynamic ATS term extraction (like your extract_required_terms — pulls terms directly from the JD text, not a fixed skill list)
    AI Match Analysis feature (like your RAG+LLM matcher — retrieves relevant resume excerpts and generates a structured "Strong Matches / Missing Areas / Recommendation" report), with a graceful rule-based fallback if no LLM API key is configured, so the app still works out-of-the-box.

Ran 4 commands, viewed 3 files, edited 3 files
Tracing function definition order and dependency issues.
You are out of free messages until 4:20 AM
Write a message…


Claude is AI and can make mistakes.
Resume intelligence pro · PY

AI Resume & Candidate Intelligence — PRO Edition (Real Extraction)
=====================================================================
A modern, SaaS-style Streamlit dashboard (dark theme, glassmorphism,
Plotly charts) for HR teams to upload resumes, chat with candidate data,
score ATS compatibility, deep-analyze resumes, compare candidates, and
browse a live-ranked leaderboard.
 
REAL DATA — NO MOCK/RANDOM VALUES:
  - PDF text extraction via `pypdf`
  - DOCX text extraction via `python-docx`
  - Skills detected via real keyword matching against extracted text
  - Experience (years) detected via regex over the actual resume text
  - Education detected via regex over the actual resume text
  - ATS score computed from real keyword overlap between resume text
    and the job description text (nothing seeded or randomized)
  - Chat answers are generated by retrieving and returning the most
    relevant sentence(s) from the candidate's actual resume text
    (simple extractive search) — replace with a real LLM call for
    higher-quality conversational answers in production.
 
Install:
    pip install streamlit pandas plotly pypdf python-docx
 
Run:
    streamlit run resume_intelligence_pro.py
"""
 
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
from datetime import datetime
from io import BytesIO
 
import hashlib
from pypdf import PdfReader
import docx  # python-docx
 
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
 
# ==================================================================================
# PAGE CONFIG
# ==================================================================================
st.set_page_config(
    page_title="AI Resume Intelligence Pro",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
# ==================================================================================
# GLOBAL CSS — Dark glassmorphic SaaS theme
# ==================================================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap');
 
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
 
    :root {
        --bg: #0b0f19;
        --panel: rgba(255,255,255,0.045);
        --panel-border: rgba(255,255,255,0.09);
        --purple: #8b5cf6;
        --teal: #14b8a6;
        --cyan: #22d3ee;
        --text: #e5e7eb;
        --muted: #94a3b8;
    }
 
    .stApp {
        background:
            radial-gradient(circle at 15% 0%, rgba(139,92,246,0.16) 0%, transparent 45%),
            radial-gradient(circle at 85% 15%, rgba(20,184,166,0.14) 0%, transparent 45%),
            var(--bg);
        color: var(--text);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] { background: transparent; }
 
    h1, h2, h3, h4, p, span, label, div { color: var(--text); }
 
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 8px; }
 
    .app-header {
        background: linear-gradient(120deg, rgba(139,92,246,0.22), rgba(20,184,166,0.18));
        border: 1px solid var(--panel-border);
        border-radius: 18px;
        padding: 1.8rem 2.2rem;
        margin-bottom: 1.6rem;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    }
    .app-title {
        font-family: 'Poppins', sans-serif;
        font-size: 2rem; font-weight: 800; margin: 0;
        background: linear-gradient(90deg, #f8fafc, #c4b5fd);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }
    .app-subtitle { color: var(--muted); font-size: 0.98rem; margin-top: 0.35rem; }
    .app-badge {
        display: inline-block; margin-top: 0.8rem;
        background: rgba(20,184,166,0.15); border: 1px solid var(--teal); color: #5eead4;
        padding: 3px 13px; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
    }
 
    .section-title {
        font-family: 'Poppins', sans-serif; font-weight: 700; font-size: 1.2rem;
        color: #f8fafc; margin-bottom: 0.15rem;
    }
    .section-caption { color: var(--muted); font-size: 0.88rem; margin-bottom: 1rem; }
 
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--panel) !important;
        border: 1px solid var(--panel-border) !important;
        border-radius: 16px !important;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 24px rgba(0,0,0,0.25);
        transition: box-shadow 0.2s ease, transform 0.2s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 8px 32px rgba(139,92,246,0.18);
    }
 
    .pill {
        display: inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: 0.76rem; font-weight: 600; margin: 3px; border: 1px solid transparent;
    }
    .pill-teal   { background: rgba(20,184,166,0.15); color: #5eead4; border-color: rgba(20,184,166,0.4); }
    .pill-red    { background: rgba(239,68,68,0.15); color: #fca5a5; border-color: rgba(239,68,68,0.4); }
    .pill-purple { background: rgba(139,92,246,0.15); color: #c4b5fd; border-color: rgba(139,92,246,0.4); }
    .pill-amber  { background: rgba(245,158,11,0.15); color: #fcd34d; border-color: rgba(245,158,11,0.4); }
 
    .avatar {
        display: inline-flex; align-items: center; justify-content: center;
        width: 42px; height: 42px; border-radius: 50%;
        background: linear-gradient(135deg, var(--purple), var(--cyan));
        color: white; font-weight: 700; font-family:'Poppins',sans-serif; font-size: 0.95rem;
        flex-shrink: 0;
    }
 
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b0f19 0%, #131a2b 100%);
        border-right: 1px solid var(--panel-border);
    }
    section[data-testid="stSidebar"] * { color: var(--text) !important; }
    section[data-testid="stSidebar"] hr { border-color: var(--panel-border); }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        background: transparent; border-radius: 10px; padding: 9px 12px; margin-bottom: 4px;
        transition: background 0.15s ease; border: 1px solid transparent;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background: rgba(255,255,255,0.06);
    }
 
    .stButton > button, .stDownloadButton > button {
        border-radius: 9px; font-weight: 600; border: 1px solid var(--panel-border);
        background: rgba(255,255,255,0.06); color: var(--text);
    }
    .stButton > button[kind="primary"], .stDownloadButton > button {
        background: linear-gradient(90deg, var(--purple), var(--teal));
        color: white; border: none;
    }
    .stButton > button:hover { transform: translateY(-1px); }
    .stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
        box-shadow: 0 6px 18px rgba(139,92,246,0.35);
    }
 
    div[data-testid="stMetric"] {
        background: var(--panel); border: 1px solid var(--panel-border); border-radius: 14px;
        padding: 0.8rem 1rem;
    }
    div[data-testid="stMetricValue"] { color: #f8fafc; }
    div[data-testid="stMetricLabel"] { color: var(--muted); }
 
    div[data-testid="stProgress"] > div > div {
        background: linear-gradient(90deg, var(--purple), var(--cyan)) !important;
    }
 
    .stTextArea textarea, .stTextInput input {
        background: rgba(255,255,255,0.04) !important;
        color: var(--text) !important;
        border: 1px solid var(--panel-border) !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="select"] > div {
        background: rgba(255,255,255,0.04) !important;
        border-color: var(--panel-border) !important;
    }
 
    button[data-baseweb="tab"] { font-weight: 600; color: var(--muted); }
    button[data-baseweb="tab"][aria-selected="true"] { color: #f8fafc; }
 
    section[data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,0.03); border: 1.5px dashed var(--panel-border); border-radius: 14px;
    }
 
    .empty-state {
        text-align: center; padding: 2.6rem 1.5rem; border: 1.5px dashed var(--panel-border);
        border-radius: 16px; background: var(--panel); color: var(--muted);
    }
    .empty-state .icon { font-size: 2.4rem; margin-bottom: 0.4rem; }
 
    div[data-testid="stChatMessage"] {
        background: var(--panel); border: 1px solid var(--panel-border); border-radius: 14px;
    }
 
    mark { background: rgba(20,184,166,0.35); color: #f0fdfa; padding: 1px 3px; border-radius: 4px; }
 
    div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)
 
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e5e7eb", family="Inter"),
    margin=dict(l=20, r=20, t=40, b=20),
)
 
 
def app_header(title, subtitle, badge):
    st.markdown(
        f"""
        <div class="app-header">
            <p class="app-title">🧠 {title}</p>
            <p class="app-subtitle">{subtitle}</p>
            <span class="app-badge">{badge}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
 
 
def empty_state(icon, title, message):
    st.markdown(
        f"""<div class="empty-state"><div class="icon">{icon}</div><b>{title}</b><br>{message}</div>""",
        unsafe_allow_html=True,
    )
 
 
def avatar(name, size=42):
    initials = "".join([p[0].upper() for p in name.split()[:2]]) or "?"
    return f'<span class="avatar" style="width:{size}px;height:{size}px;">{initials}</span>'
 
 
# ==================================================================================
# SESSION STATE
# ==================================================================================
def init_state():
    defaults = {
        "candidates": {},   # {name: {file_name, text, skills, exp_years, education, competencies}}
        "job_description": "",
        "chat_history": [],
        "chat_target": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
 
init_state()
 
# ==================================================================================
# REFERENCE TAXONOMY (used only to RECOGNIZE real skills in text — not to fabricate data)
# ==================================================================================
SKILL_POOL = [
    "Python", "Java", "C++", "JavaScript", "TypeScript", "SQL", "R",
    "Machine Learning", "Deep Learning", "Data Analysis", "Data Science",
    "Project Management", "Product Management", "Communication", "Leadership",
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "React", "Angular", "Node.js",
    "Excel", "Tableau", "Power BI", "Stakeholder Management", "Agile", "Scrum",
    "Negotiation", "Customer Service", "Public Speaking", "Git", "REST API",
    "NLP", "Computer Vision", "TensorFlow", "PyTorch", "Django", "Flask",
]
 
COMPETENCY_GROUPS = {
    "Technical Skills": ["Python", "Java", "C++", "JavaScript", "TypeScript", "SQL", "R",
                          "Machine Learning", "Deep Learning", "AWS", "Azure", "GCP",
                          "Docker", "Kubernetes", "React", "Angular", "Node.js", "Git",
                          "REST API", "NLP", "Computer Vision", "TensorFlow", "PyTorch",
                          "Django", "Flask"],
    "Data & Analytics": ["Data Analysis", "Data Science", "Excel", "Tableau", "Power BI"],
    "Leadership": ["Leadership", "Project Management", "Product Management", "Stakeholder Management"],
    "Communication": ["Communication", "Public Speaking", "Negotiation", "Customer Service"],
    "Process & Delivery": ["Agile", "Scrum"],
}
 
EDUCATION_PATTERNS = [
    r"(Ph\.?D\.?[^\n,.]{0,60})",
    r"(M\.?B\.?A\.?[^\n,.]{0,60})",
    r"(M\.?S\.?c?\.?\s+in\s+[A-Za-z &]+)",
    r"(M\.?Tech\.?[^\n,.]{0,60})",
    r"(B\.?Tech\.?[^\n,.]{0,60})",
    r"(B\.?S\.?c?\.?\s+in\s+[A-Za-z &]+)",
    r"(B\.?A\.?\s+in\s+[A-Za-z &]+)",
    r"(Bachelor(?:'s)?\s+(?:of|in)\s+[A-Za-z &]+)",
    r"(Master(?:'s)?\s+(?:of|in)\s+[A-Za-z &]+)",
]
 
EXPERIENCE_PATTERNS = [
    r"(\d{1,2})\+?\s*years?\s+(?:of\s+)?experience",
    r"experience\s*[:\-]?\s*(\d{1,2})\+?\s*years?",
]
 
# ==================================================================================
# REAL TEXT EXTRACTION
# ==================================================================================
def extract_text_from_pdf(uploaded_file) -> str:
    """Extract raw text from a PDF. Tries pypdf first; falls back to
    pdfplumber (handles some layouts pypdf misses). If both return
    empty, the PDF is very likely a SCANNED IMAGE with no real text
    layer — in that case OCR (e.g. pytesseract) would be required,
    which this app does not perform."""
    raw_bytes = uploaded_file.getvalue()
    text = ""
 
    # Attempt 1: pypdf
    try:
        reader = PdfReader(BytesIO(raw_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages_text).strip()
    except Exception:
        text = ""
 
    # Attempt 2: pdfplumber fallback if pypdf got nothing usable
    if len(text) < 30 and PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(BytesIO(raw_bytes)) as pdf:
                pages_text = [(p.extract_text() or "") for p in pdf.pages]
            fallback_text = "\n".join(pages_text).strip()
            if len(fallback_text) > len(text):
                text = fallback_text
        except Exception:
            pass
 
    return text
 
 
def extract_text_from_docx(uploaded_file) -> str:
    """Extract raw text from a DOCX using python-docx."""
    try:
        document = docx.Document(BytesIO(uploaded_file.getvalue()))
        paragraphs = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    paragraphs.append(cell.text)
        return "\n".join([p for p in paragraphs if p.strip()]).strip()
    except Exception:
        return ""
 
 
def extract_text(uploaded_file) -> str:
    """Route to the correct real extractor based on file extension."""
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(uploaded_file)
    elif name.endswith(".docx"):
        return extract_text_from_docx(uploaded_file)
    return uploaded_file.getvalue().decode("utf-8", errors="ignore")
 
 
def file_content_hash(uploaded_file) -> str:
    """Hash the actual file bytes so re-uploading the same-named file
    with different content is always treated as a fresh candidate."""
    return hashlib.md5(uploaded_file.getvalue()).hexdigest()[:10]
 
 
# ==================================================================================
# REAL PROFILE PARSING (regex / keyword matching over actual extracted text)
# ==================================================================================
def detect_skills(text: str):
    """Return taxonomy skills that literally appear in the resume text."""
    found = []
    for skill in SKILL_POOL:
        pattern = r"\b" + re.escape(skill).replace(r"\ ", r"[\s\-]?") + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            found.append(skill)
    return sorted(set(found))
 
 
def detect_experience_years(text: str) -> int:
    """Parse explicit 'X years of experience' style phrases from the text."""
    for pattern in EXPERIENCE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue
    return 0  # Unknown / not stated in the document
 
 
def detect_education(text: str) -> str:
    """Find the first recognizable education/degree phrase in the text."""
    for pattern in EDUCATION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(" .,-")
    return "Not specified in document"
 
 
def compute_competencies(skills):
    """Score each competency group by the real proportion of its taxonomy skills found."""
    scores = {}
    for group, group_skills in COMPETENCY_GROUPS.items():
        present = [s for s in group_skills if s in skills]
        scores[group] = round((len(present) / len(group_skills)) * 100) if group_skills else 0
    return scores
 
 
def build_profile(text: str):
    skills = detect_skills(text)
    exp_years = detect_experience_years(text)
    education = detect_education(text)
    competencies = compute_competencies(skills)
    return skills, exp_years, education, competencies
 
 
# ==================================================================================
# REAL ATS SCORING — TAXONOMY-BASED (keyword overlap against a fixed skill list)
# ==================================================================================
def ats_score(resume_skills, resume_text, job_description: str):
    """Compute ATS match purely from keyword overlap; deterministic, no randomness."""
    if not job_description.strip():
        return 0, [], []
 
    jd_lower = job_description.lower()
    jd_required_skills = [s for s in SKILL_POOL if re.search(
        r"\b" + re.escape(s).replace(r"\ ", r"[\s\-]?") + r"\b", jd_lower, re.IGNORECASE
    )]
 
    if not jd_required_skills:
        return 0, [], []
 
    matched = [s for s in jd_required_skills if s in resume_skills]
    missing = [s for s in jd_required_skills if s not in resume_skills]
    score = round((len(matched) / len(jd_required_skills)) * 100)
    return score, matched, missing
 
 
# ==================================================================================
# DYNAMIC ATS SCORING — JD-DERIVED TERMS (no fixed skill list — every meaningful
# word/term is pulled straight out of the actual job description text)
# ==================================================================================
JD_STOPWORDS = {
    "and", "the", "for", "with", "from", "that", "this", "will", "have", "has",
    "are", "you", "your", "our", "job", "role", "work", "working", "experience",
    "years", "year", "using", "use", "ability", "required", "requirements",
    "candidate", "team", "strong", "good", "knowledge", "skills",
    "responsibilities", "including", "etc", "such", "who", "can", "must",
    "should", "into", "across", "within", "other", "any", "all", "well",
    "plus", "preferred", "looking", "seeking", "join", "about",
}
 
 
def normalize_text(text: str) -> str:
    """Lowercase and collapse whitespace, exactly like ATS_score.py's normalize_text."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()
 
 
def extract_required_terms(job_description: str):
    """Pull every meaningful term directly out of the JD text — no manual/fixed
    skill list needed. Mirrors the term-extraction approach from ATS_score.py."""
    normalized = normalize_text(job_description)
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.\-]*\b", normalized)
    required_terms = []
    for word in words:
        if len(word) > 2 and word not in JD_STOPWORDS and word not in required_terms:
            required_terms.append(word)
    return required_terms
 
 
def term_exists(term: str, resume_text: str) -> bool:
    """Check whether a required term literally appears in the resume text."""
    return normalize_text(term) in normalize_text(resume_text)
 
 
def calculate_term_match(required_terms, resume_text: str):
    """Split JD-derived terms into matched vs. missing against the resume text."""
    matched_terms, missing_terms = [], []
    for term in required_terms:
        (matched_terms if term_exists(term, resume_text) else missing_terms).append(term)
    return matched_terms, missing_terms
 
 
def calculate_dynamic_ats_score(required_terms, matched_terms) -> float:
    """Percentage of JD-derived terms found verbatim in the resume text."""
    if not required_terms:
        return 0.0
    return round((len(matched_terms) / len(required_terms)) * 100, 2)
 
 
def get_score_category(score: float) -> str:
    if score >= 80:
        return "Strong Match"
    elif score >= 60:
        return "Moderate Match"
    elif score >= 40:
        return "Weak Match"
    else:
        return "Poor Match"
 
 
def dynamic_ats_score(resume_text: str, job_description: str):
    """Full dynamic ATS pipeline: extract JD terms, match against resume text,
    score, and categorize. Returns (score, category, matched, missing)."""
    if not job_description.strip():
        return 0.0, "No JD", [], []
    required_terms = extract_required_terms(job_description)
    matched_terms, missing_terms = calculate_term_match(required_terms, resume_text)
    score = calculate_dynamic_ats_score(required_terms, matched_terms)
    category = get_score_category(score)
    return score, category, matched_terms, missing_terms
 
 
def generate_suggestions(missing, exp_years, education):
    """Data-driven suggestions based on the actual gaps detected — no canned randomness."""
    tips = []
    if missing:
        tips.append(f"Add concrete, measurable achievements demonstrating **{missing[0]}**.")
        if len(missing) > 1:
            tips.append(f"Consider incorporating **{', '.join(missing[1:4])}** if genuinely applicable to your background.")
    if exp_years == 0:
        tips.append("State your years of experience explicitly (e.g. '5 years of experience in...') so it can be parsed by ATS systems.")
    if education == "Not specified in document":
        tips.append("Add a clear Education section with your degree title (e.g. 'B.Tech in Computer Science').")
    tips.append("Quantify impact with metrics (e.g. '% improved', '$ saved', 'time reduced') wherever possible.")
    if not tips:
        tips.append("Strong alignment detected — no major gaps found against this job description.")
    return tips
 
 
# ==================================================================================
# AI MATCH ANALYSIS — retrieval of relevant resume excerpts + optional LLM report
# ==================================================================================
def retrieve_relevant_excerpts(job_description: str, resume_text: str, top_k: int = 6):
    """Extractive retrieval: rank resume sentences by keyword overlap with the JD
    (stand-in for the Qdrant vector-similarity retrieval step)."""
    sentences = split_sentences(resume_text)
    if not sentences:
        return []
    jd_words = set(re.findall(r"[a-zA-Z]{3,}", job_description.lower())) - JD_STOPWORDS
    scored = []
    for s in sentences:
        s_words = set(re.findall(r"[a-zA-Z]{3,}", s.lower()))
        overlap = len(jd_words & s_words)
        if overlap > 0:
            scored.append((overlap, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:top_k]]
 
 
def build_match_prompt(candidate_name, job_description, score, category, matched, missing, context):
    """Same structured prompt/report format as your ATS + RAG script."""
    return f"""You are an AI Hiring Assistant.
 
Analyze how well the candidate matches the provided Job Description.
 
Candidate: {candidate_name}
ATS Match Score: {score}%
Match Category: {category}
 
Matched JD Terms: {", ".join(matched) if matched else "None"}
Missing JD Terms: {", ".join(missing) if missing else "None"}
 
Job Description:
{job_description}
 
Relevant Resume Information:
{context}
 
IMPORTANT RULES:
1. Use ONLY the provided resume information.
2. Do NOT invent skills, experience, projects, companies, education, certifications, technologies, or achievements.
3. Do not assume a missing term means the candidate definitely lacks that skill — say it is not clearly mentioned in the resume.
4. Explain why the matched skills are relevant to the Job Description.
5. Identify weak or missing areas.
6. Do not change or recalculate the ATS score.
7. Give a practical hiring recommendation.
 
Use this format:
 
Candidate: {candidate_name}
Match Score: {score}%
 
Strong Matches:
- <skill and evidence>
 
Relevant Experience:
- <resume evidence relevant to the JD>
 
Missing / Weak Areas:
- <missing or unclear requirement>
 
Recommendation:
<short hiring recommendation>
 
Give a concise, professional answer."""
 
 
def call_llm_match_analysis(prompt: str, api_key: str, base_url: str, model: str) -> str:
    """Call an OpenAI-compatible chat endpoint (works with OpenRouter, OpenAI, etc.)."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=700,
    )
    return response.choices[0].message.content
 
 
def fallback_match_analysis(candidate_name, score, category, matched, missing, context):
    """Rule-based report used when no LLM API key is configured — no external
    calls required, so this feature always works out of the box."""
    strong = "\n".join([f"- **{t}** appears in the resume text." for t in matched[:8]]) or "- No strong keyword matches found."
    weak = "\n".join([f"- **{t}** not clearly mentioned in the resume." for t in missing[:8]]) or "- No significant gaps found."
    evidence = "\n".join([f"- {s}" for s in context[:5]]) or "- No directly relevant excerpts were found."
 
    if category == "Strong Match":
        recommendation = "Strong alignment with the role — recommended to advance to the next interview stage."
    elif category == "Moderate Match":
        recommendation = "Reasonable fit with some gaps — consider a screening call to probe the missing areas."
    elif category == "Weak Match":
        recommendation = "Limited alignment — likely not a fit unless the missing areas are addressed elsewhere (e.g. a cover letter)."
    else:
        recommendation = "Poor alignment with the job description as written — not recommended to proceed."
 
    return f"""**Candidate:** {candidate_name}
**Match Score:** {score}% ({category})
 
**Strong Matches:**
{strong}
 
**Relevant Experience (extracted from resume):**
{evidence}
 
**Missing / Weak Areas:**
{weak}
 
**Recommendation:**
{recommendation}
 
*(Rule-based report — no LLM API key configured. Add one in the sidebar for a richer, AI-generated narrative.)*"""
 
 
 
# ==================================================================================
def split_sentences(text: str):
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 15]
 
 
def chat_answer(question: str, resume_text: str) -> str:
    """Return the most relevant sentence(s) from the actual resume text
    based on keyword overlap with the question. Purely extractive — swap
    for a real LLM call (e.g. the Anthropic API) for richer answers."""
    sentences = split_sentences(resume_text)
    if not sentences:
        return "I couldn't find readable text in this resume to answer from."
 
    question_words = set(re.findall(r"[a-zA-Z]{3,}", question.lower()))
    stopwords = {"the", "and", "for", "are", "does", "did", "has", "have", "with",
                 "about", "what", "when", "where", "who", "how", "this", "that", "you"}
    question_words -= stopwords
 
    scored = []
    for s in sentences:
        s_words = set(re.findall(r"[a-zA-Z]{3,}", s.lower()))
        overlap = len(question_words & s_words)
        if overlap > 0:
            scored.append((overlap, s))
 
    if not scored:
        for skill in SKILL_POOL:
            if skill.lower() in question.lower() and skill.lower() in resume_text.lower():
                return f"Yes — **{skill}** appears directly in this candidate's resume."
        return "I couldn't find anything in this resume directly related to that question."
 
    scored.sort(key=lambda x: x[0], reverse=True)
    top_sentences = [s for _, s in scored[:2]]
    return " ".join(top_sentences)
 
 
def highlight_keywords(text, keywords):
    highlighted = text
    for kw in sorted(set(keywords), key=len, reverse=True):
        pattern = re.compile(r"\b" + re.escape(kw).replace(r"\ ", r"[\s\-]?") + r"\b", re.IGNORECASE)
        highlighted = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", highlighted)
    return highlighted
 
 
# ---------------- Plotly chart builders ----------------
def gauge_chart(score):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": "%", "font": {"size": 40, "color": "#f8fafc"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#94a3b8"},
            "bar": {"color": "#8b5cf6"},
            "bgcolor": "rgba(255,255,255,0.04)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 50], "color": "rgba(239,68,68,0.25)"},
                {"range": [50, 75], "color": "rgba(245,158,11,0.25)"},
                {"range": [75, 100], "color": "rgba(20,184,166,0.25)"},
            ],
        },
    ))
    fig.update_layout(height=260, **PLOTLY_LAYOUT)
    return fig
 
 
def radar_chart(data_dict, name, color="#8b5cf6"):
    categories = list(data_dict.keys())
    values = list(data_dict.values())
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]], theta=categories + [categories[0]],
        fill="toself", name=name, line_color=color,
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(255,255,255,0.02)",
            radialaxis=dict(visible=True, range=[0, 100], color="#94a3b8", gridcolor="#334155"),
            angularaxis=dict(color="#e5e7eb", gridcolor="#334155"),
        ),
        showlegend=True, height=340, **PLOTLY_LAYOUT,
    )
    return fig
 
 
def dual_radar_chart(dict_a, name_a, dict_b, name_b):
    categories = list(dict_a.keys())
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=list(dict_a.values()) + [list(dict_a.values())[0]], theta=categories + [categories[0]],
        fill="toself", name=name_a, line_color="#8b5cf6",
    ))
    fig.add_trace(go.Scatterpolar(
        r=list(dict_b.values()) + [list(dict_b.values())[0]], theta=categories + [categories[0]],
        fill="toself", name=name_b, line_color="#22d3ee",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(255,255,255,0.02)",
            radialaxis=dict(visible=True, range=[0, 100], color="#94a3b8", gridcolor="#334155"),
            angularaxis=dict(color="#e5e7eb", gridcolor="#334155"),
        ),
        showlegend=True, height=380,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15), **PLOTLY_LAYOUT,
    )
    return fig
 
 
def ranking_bar_chart(df):
    fig = go.Figure(go.Bar(
        x=df["ATS Score (%)"], y=df["Candidate"], orientation="h",
        marker=dict(
            color=df["ATS Score (%)"],
            colorscale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#14b8a6"]],
            line=dict(width=0),
        ),
        text=df["ATS Score (%)"].astype(str) + "%",
        textposition="outside",
    ))
    fig.update_layout(
        height=100 + 45 * len(df),
        xaxis=dict(range=[0, 105], gridcolor="#1f2937", title="ATS Score (%)"),
        yaxis=dict(autorange="reversed"),
        **PLOTLY_LAYOUT,
    )
    return fig
 
 
# ==================================================================================
# SIDEBAR NAVIGATION
# ==================================================================================
st.sidebar.markdown(
    """
    <div style="text-align:center; padding: 0.4rem 0 1rem 0;">
        <div style="font-size:2.2rem;">🧠</div>
        <div style="font-family:'Poppins',sans-serif; font-size:1.2rem; font-weight:800;">
            Resume Intelligence
        </div>
        <div style="font-size:0.76rem; color:#5eead4; margin-top:2px; letter-spacing:0.5px;">PRO EDITION</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.divider()
 
FEATURES = [
    "🏠 Dashboard",
    "📤 Upload Resume",
    "📋 Upload Job Description",
    "💬 Chat with Resumes",
    "🎯 ATS Resume Matcher",
    "🤖 AI Match Analysis",
    "🔬 Resume Analyzer",
    "⚖️ Candidate Comparison",
    "🏆 Candidate Ranking",
]
feature = st.sidebar.radio("Select Feature", FEATURES, label_visibility="collapsed")
 
st.sidebar.divider()
st.sidebar.markdown("###### 📊 SESSION STATUS")
c1, c2 = st.sidebar.columns(2)
c1.metric("Candidates", len(st.session_state.candidates))
c2.metric("JD Ready", "✅" if st.session_state.job_description else "—")
 
st.sidebar.divider()
with st.sidebar.expander("🤖 AI Match Analysis Settings"):
    st.caption("Optional — add an OpenAI-compatible API key (e.g. OpenAI, OpenRouter) to generate rich AI narratives. Without a key, a rule-based report is used instead.")
    st.session_state.llm_api_key = st.text_input("API Key", type="password", value=st.session_state.get("llm_api_key", ""))
    st.session_state.llm_base_url = st.text_input("Base URL (optional)", value=st.session_state.get("llm_base_url", ""), placeholder="https://openrouter.ai/api/v1")
    st.session_state.llm_model = st.text_input("Model", value=st.session_state.get("llm_model", "gpt-4o-mini"))
 
st.sidebar.divider()
st.sidebar.caption(f"🕒 {datetime.now().strftime('%b %d, %Y · %I:%M %p')}")
 
# ==================================================================================
# FEATURE 0 — DASHBOARD OVERVIEW
# ==================================================================================
if feature == "🏠 Dashboard":
    app_header("AI Resume Intelligence Pro", "Your real-time hiring command center", "🏠 Overview")
 
    cands = st.session_state.candidates
    jd = st.session_state.job_description
 
    scored = []
    if cands and jd:
        for key, data in cands.items():
            score, matched, missing = ats_score(data["skills"], data["text"], jd)
            scored.append((data["display_name"], score))
    avg_score = round(sum(s for _, s in scored) / len(scored)) if scored else 0
    top_candidate = max(scored, key=lambda x: x[1])[0] if scored else "—"
 
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("👥 Candidates", len(cands))
    k2.metric("📋 JD Status", "Ready" if jd else "Missing")
    k3.metric("📈 Avg ATS Score", f"{avg_score}%" if scored else "—")
    k4.metric("🏆 Top Candidate", top_candidate)
 
    st.write("")
    col1, col2 = st.columns([2, 1])
 
    with col1:
        with st.container(border=True):
            st.markdown('<p class="section-title">📊 Candidate Score Overview</p>', unsafe_allow_html=True)
            if scored:
                df = pd.DataFrame(scored, columns=["Candidate", "ATS Score (%)"]).sort_values(
                    "ATS Score (%)", ascending=False
                )
                st.plotly_chart(ranking_bar_chart(df), use_container_width=True, config={"displayModeBar": False})
            else:
                empty_state("📊", "No score data yet", "Upload resumes and a job description to see live scoring.")
 
    with col2:
        with st.container(border=True):
            st.markdown('<p class="section-title">🧭 Quick Actions</p>', unsafe_allow_html=True)
            st.markdown("- 📤 Upload more resumes\n- 📋 Refine job description\n- 💬 Chat about a candidate\n- 🏆 View full leaderboard")
            st.write("")
            st.markdown('<p class="section-title">👥 Recent Candidates</p>', unsafe_allow_html=True)
            if cands:
                for key in list(cands.keys())[-4:][::-1]:
                    disp = cands[key]["display_name"]
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">{avatar(disp, 34)}'
                        f'<span>{disp}</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No candidates uploaded yet.")
 
# ==================================================================================
# FEATURE 1 — UPLOAD RESUME (real extraction)
# ==================================================================================
elif feature == "📤 Upload Resume":
    app_header("Resume Intake", "Upload candidate resumes to build your talent pool", "📤 Step 1")
 
    with st.container(border=True):
        st.markdown('<p class="section-title">Upload Candidate Resumes</p>', unsafe_allow_html=True)
        st.markdown('<p class="section-caption">Supports PDF and DOCX. Text, skills, experience, and education are parsed directly from the file — nothing is fabricated.</p>', unsafe_allow_html=True)
        files = st.file_uploader("Drag and drop resume files", type=["pdf", "docx"],
                                  accept_multiple_files=True, label_visibility="collapsed")
        if files:
            new_count = 0
            for f in files:
                base_name = f.name.rsplit(".", 1)[0].replace("_", " ").title()
                content_hash = file_content_hash(f)
                # Key candidates by name + content hash so a re-uploaded or
                # edited file is ALWAYS freshly re-parsed, never reused from
                # a stale/previous session entry.
                candidate_key = f"{base_name} [{content_hash}]"
                if candidate_key not in st.session_state.candidates:
                    with st.spinner(f"Parsing {f.name}..."):
                        text = extract_text(f)
                        skills, exp_years, education, comp = build_profile(text)
                    st.session_state.candidates[candidate_key] = {
                        "display_name": base_name, "file_name": f.name, "text": text,
                        "skills": skills, "exp_years": exp_years, "education": education,
                        "competencies": comp,
                    }
                    new_count += 1
            if new_count:
                st.success(f"✅ Successfully processed {new_count} new resume(s)!")
 
        if st.session_state.candidates:
            if st.button("🗑️ Clear All Candidates (reset)", use_container_width=False):
                st.session_state.candidates = {}
                st.session_state.chat_history = []
                st.rerun()
 
    st.write("")
    if st.session_state.candidates:
        st.markdown('<p class="section-title">Candidate Pool</p>', unsafe_allow_html=True)
        cols = st.columns(3)
        for i, (key, data) in enumerate(st.session_state.candidates.items()):
            display_name = data.get("display_name", key)
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;">{avatar(display_name)}'
                        f'<div><b>{display_name}</b><br><span style="font-size:0.78rem;color:#94a3b8;">📎 {data["file_name"]}</span></div></div>',
                        unsafe_allow_html=True,
                    )
                    st.write("")
 
                    if not data["text"] or len(data["text"].strip()) < 30:
                        st.error("⚠️ No readable text could be extracted from this file. It's likely a **scanned image PDF** (no real text layer) — this app cannot OCR images. Try a text-based export of the resume instead.")
                    else:
                        exp_display = f"{data['exp_years']} yrs experience" if data["exp_years"] else "Experience not stated"
                        st.markdown(f"🧳 {exp_display}")
                        if data["skills"]:
                            st.markdown(
                                " ".join([f'<span class="pill pill-teal">{s}</span>' for s in data["skills"][:4]]),
                                unsafe_allow_html=True,
                            )
                        else:
                            st.caption("No taxonomy skills detected in this document's text.")
 
                    with st.expander("📄 View raw extracted text (verify this matches your file)"):
                        st.text_area("preview", data["text"][:3000] or "(No text could be extracted — see warning above)",
                                      height=180, disabled=True, label_visibility="collapsed", key=f"prev_{key}")
                    if st.button("🗑️ Remove", key=f"rm_{key}", use_container_width=True):
                        del st.session_state.candidates[key]
                        st.rerun()
    else:
        empty_state("📄", "No resumes uploaded yet", "Upload PDF or DOCX files above to build your candidate pool.")
 
# ==================================================================================
# FEATURE 2 — UPLOAD JOB DESCRIPTION
# ==================================================================================
elif feature == "📋 Upload Job Description":
    app_header("Job Description Intake", "Define the target role so candidates can be scored against it", "📋 Step 2")
 
    tab1, tab2 = st.tabs(["✏️ Paste Text", "📁 Upload File"])
    with tab1:
        with st.container(border=True):
            jd_text = st.text_area("Job description", value=st.session_state.job_description, height=240,
                                    placeholder="Paste the full job description here...",
                                    label_visibility="collapsed")
            if st.button("💾 Save Job Description", type="primary"):
                st.session_state.job_description = jd_text
                st.success("Job description saved!")
                st.rerun()
 
    with tab2:
        with st.container(border=True):
            jd_file = st.file_uploader("Upload JD file", type=["pdf", "docx", "txt"], label_visibility="collapsed")
            if jd_file:
                with st.spinner(f"Extracting text from {jd_file.name}..."):
                    if jd_file.name.lower().endswith(".txt"):
                        content = jd_file.getvalue().decode("utf-8", errors="ignore")
                    else:
                        content = extract_text(jd_file)
                st.session_state.job_description = content
                st.success(f"✅ Loaded job description from **{jd_file.name}**")
                st.rerun()
 
    st.write("")
    if st.session_state.job_description:
        with st.container(border=True):
            st.markdown('<p class="section-title">🔦 Keyword Highlight Preview</p>', unsafe_allow_html=True)
            st.markdown('<p class="section-caption">Skills from our taxonomy detected directly inside the JD text are highlighted.</p>', unsafe_allow_html=True)
            found = [s for s in SKILL_POOL if re.search(
                r"\b" + re.escape(s).replace(r"\ ", r"[\s\-]?") + r"\b",
                st.session_state.job_description, re.IGNORECASE
            )]
            st.markdown(highlight_keywords(st.session_state.job_description, found), unsafe_allow_html=True)
            st.markdown(
                " ".join([f'<span class="pill pill-teal">{s}</span>' for s in found]) or "_No taxonomy skills detected in this JD._",
                unsafe_allow_html=True,
            )
    else:
        empty_state("📋", "No job description set", "Paste or upload a JD above to enable ATS matching and comparisons.")
 
# ==================================================================================
# FEATURE 3 — CHAT WITH RESUMES (real extractive search over parsed text)
# ==================================================================================
elif feature == "💬 Chat with Resumes":
    app_header("Chat with Resumes", "Ask questions and get answers pulled directly from the resume text", "💬 Extractive Search")
 
    if not st.session_state.candidates:
        empty_state("💬", "No resumes to chat with", "Upload at least one resume in the 'Upload Resume' tab first.")
    else:
        candidate = st.selectbox("Select a candidate", list(st.session_state.candidates.keys()),
                                  format_func=lambda k: st.session_state.candidates[k]["display_name"])
        st.session_state.chat_target = candidate
 
        with st.container(border=True, height=420):
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
 
        candidate_display = st.session_state.candidates[candidate]["display_name"]
        user_q = st.chat_input(f"Ask something about {candidate_display}'s resume...")
        if user_q:
            st.session_state.chat_history.append({"role": "user", "content": user_q})
            resume_text = st.session_state.candidates[candidate]["text"]
            reply = chat_answer(user_q, resume_text)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.rerun()
 
        if st.button("🧹 Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()
 
# ==================================================================================
# FEATURE 4 — ATS RESUME MATCHER (real keyword overlap)
# ==================================================================================
elif feature == "🎯 ATS Resume Matcher":
    app_header("ATS Resume Matcher", "See how well a resume matches the job description", "🎯 ATS Scoring Engine")
 
    if not st.session_state.candidates:
        empty_state("📄", "No resumes uploaded", "Upload resumes first to run the ATS matcher.")
    elif not st.session_state.job_description:
        empty_state("📋", "No job description set", "Add a job description first so we have something to match against.")
    else:
        candidate = st.selectbox("Select candidate", list(st.session_state.candidates.keys()),
                                  format_func=lambda k: st.session_state.candidates[k]["display_name"])
        data = st.session_state.candidates[candidate]
 
        mode = st.radio(
            "Scoring mode",
            ["🏷️ Taxonomy Skills", "🔎 Dynamic JD Terms"],
            horizontal=True,
            help="Taxonomy Skills scores against a curated skill list. Dynamic JD Terms extracts EVERY meaningful term straight from your job description text — no fixed list required.",
        )
 
        if mode == "🏷️ Taxonomy Skills":
            score, matched, missing = ats_score(data["skills"], data["text"], st.session_state.job_description)
            category = None
        else:
            score, category, matched, missing = dynamic_ats_score(data["text"], st.session_state.job_description)
 
        col1, col2 = st.columns([1, 2])
        with col1:
            with st.container(border=True):
                st.markdown('<p class="section-title">Overall Match</p>', unsafe_allow_html=True)
                st.plotly_chart(gauge_chart(score), use_container_width=True, config={"displayModeBar": False})
                if category:
                    st.caption(f"Category: **{category}**")
                if score >= 75:
                    st.success("Excellent match ✅")
                elif score >= 50:
                    st.warning("Moderate match — tailoring recommended")
                else:
                    st.error("Low match — significant gaps")
 
        with col2:
            with st.container(border=True):
                st.markdown('<p class="section-title">Keyword Breakdown</p>', unsafe_allow_html=True)
                st.caption(f"{len(matched)} matched · {len(missing)} missing" + (" (all terms extracted directly from your JD text)" if mode == "🔎 Dynamic JD Terms" else ""))
                st.markdown("**✅ Matching Keywords**")
                st.markdown(
                    " ".join([f'<span class="pill pill-teal">{s}</span>' for s in matched]) or "_None found_",
                    unsafe_allow_html=True,
                )
                st.markdown("**❌ Missing Keywords**")
                st.markdown(
                    " ".join([f'<span class="pill pill-red">{s}</span>' for s in missing]) or "_None — full coverage!_",
                    unsafe_allow_html=True,
                )
 
# ==================================================================================
# FEATURE — AI MATCH ANALYSIS (JD-derived scoring + resume excerpt retrieval +
# optional LLM narrative report, rule-based fallback if no API key configured)
# ==================================================================================
elif feature == "🤖 AI Match Analysis":
    app_header("AI Match Analysis", "Structured hiring analysis grounded strictly in the resume text", "🤖 RAG-style Matching")
 
    if not st.session_state.candidates:
        empty_state("🤖", "No resumes uploaded", "Upload resumes first to run AI match analysis.")
    elif not st.session_state.job_description:
        empty_state("📋", "No job description set", "Add a job description first so we have something to match against.")
    else:
        candidate = st.selectbox("Select candidate", list(st.session_state.candidates.keys()),
                                  format_func=lambda k: st.session_state.candidates[k]["display_name"],
                                  key="ai_match_candidate")
        data = st.session_state.candidates[candidate]
        display_name = data["display_name"]
 
        if st.button("🚀 Run AI Match Analysis", type="primary"):
            with st.spinner("Extracting JD terms, retrieving relevant resume excerpts, and scoring..."):
                score, category, matched, missing = dynamic_ats_score(data["text"], st.session_state.job_description)
                excerpts = retrieve_relevant_excerpts(st.session_state.job_description, data["text"])
                context = "\n\n".join(excerpts) if excerpts else "No relevant resume information was retrieved."
 
                api_key = st.session_state.get("llm_api_key", "")
                if api_key:
                    try:
                        prompt = build_match_prompt(display_name, st.session_state.job_description,
                                                     score, category, matched, missing, context)
                        report = call_llm_match_analysis(
                            prompt, api_key,
                            st.session_state.get("llm_base_url", ""),
                            st.session_state.get("llm_model", "gpt-4o-mini"),
                        )
                    except Exception as e:
                        st.warning(f"LLM call failed ({e}) — showing rule-based report instead.")
                        report = fallback_match_analysis(display_name, score, category, matched, missing, excerpts)
                else:
                    report = fallback_match_analysis(display_name, score, category, matched, missing, excerpts)
 
            m1, m2, m3 = st.columns(3)
            m1.metric("Match Score", f"{score}%")
            m2.metric("Category", category)
            m3.metric("Terms Matched", f"{len(matched)}/{len(matched) + len(missing)}")
 
            st.write("")
            with st.container(border=True):
                st.markdown('<p class="section-title">📋 AI Match Report</p>', unsafe_allow_html=True)
                st.markdown(report)
 
            with st.expander("🔎 Retrieved resume excerpts used for this analysis"):
                if excerpts:
                    for e in excerpts:
                        st.markdown(f"- {e}")
                else:
                    st.caption("No relevant excerpts were found in this resume.")
        else:
            st.info("Click **Run AI Match Analysis** to generate a structured hiring report grounded strictly in the candidate's actual resume text.")
 
# ==================================================================================
# FEATURE 5 — RESUME ANALYZER (real breakdown)
# ==================================================================================
elif feature == "🔬 Resume Analyzer":
    app_header("Resume Analyzer", "Deep-dive breakdown of a candidate's profile", "🔬 Deep Insights")
 
    if not st.session_state.candidates:
        empty_state("🔬", "No resumes to analyze", "Upload a resume first in the 'Upload Resume' tab.")
    else:
        candidate = st.selectbox("Select candidate to analyze", list(st.session_state.candidates.keys()),
                                  format_func=lambda k: st.session_state.candidates[k]["display_name"])
        data = st.session_state.candidates[candidate]
        score, matched, missing = ats_score(data["skills"], data["text"], st.session_state.job_description)
        tips = generate_suggestions(missing, data["exp_years"], data["education"])
 
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Experience", f"{data['exp_years']} yrs" if data["exp_years"] else "Not stated")
        m2.metric("Skills Found", len(data["skills"]))
        m3.metric("JD Match", f"{score}%" if st.session_state.job_description else "—")
        m4.metric("Missing Skills", len(missing) if st.session_state.job_description else "—")
 
        st.write("")
        c1, c2 = st.columns([1, 1])
        with c1:
            with st.container(border=True):
                st.markdown('<p class="section-title">🕸️ Competency Radar</p>', unsafe_allow_html=True)
                st.caption("Score = % of each competency's taxonomy skills found in this resume.")
                st.plotly_chart(radar_chart(data["competencies"], candidate), use_container_width=True, config={"displayModeBar": False})
            with st.container(border=True):
                st.markdown('<p class="section-title">🎓 Education</p>', unsafe_allow_html=True)
                st.write(data["education"])
 
        with c2:
            with st.container(border=True):
                st.markdown('<p class="section-title">🧠 Extracted Skills</p>', unsafe_allow_html=True)
                if data["skills"]:
                    st.markdown(
                        " ".join([f'<span class="pill pill-teal">{s}</span>' for s in data["skills"]]),
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("No taxonomy skills detected in this document's text.")
            with st.container(border=True):
                st.markdown('<p class="section-title">💡 Improvement Suggestions</p>', unsafe_allow_html=True)
                for t in tips:
                    st.markdown(f"- {t}")
            with st.container(border=True):
                st.markdown('<p class="section-title">📄 Resume Preview</p>', unsafe_allow_html=True)
                st.text_area("preview", data["text"][:2000] or "(No text could be extracted)",
                              height=120, disabled=True, label_visibility="collapsed")
 
# ==================================================================================
# FEATURE 6 — CANDIDATE COMPARISON
# ==================================================================================
elif feature == "⚖️ Candidate Comparison":
    app_header("Candidate Comparison", "Compare two candidates side-by-side across core competencies", "⚖️ Head-to-Head")
 
    if len(st.session_state.candidates) < 2:
        empty_state("⚖️", "Need at least 2 candidates", "Upload two or more resumes to unlock comparison view.")
    else:
        names = list(st.session_state.candidates.keys())
        name_fmt = lambda k: st.session_state.candidates[k]["display_name"]
        s1, s2 = st.columns(2)
        cand_a = s1.selectbox("Candidate A", names, index=0, format_func=name_fmt)
        cand_b = s2.selectbox("Candidate B", names, index=1 if len(names) > 1 else 0, format_func=name_fmt)
 
        data_a = st.session_state.candidates[cand_a]
        data_b = st.session_state.candidates[cand_b]
 
        with st.container(border=True):
            st.markdown('<p class="section-title">🕸️ Competency Comparison</p>', unsafe_allow_html=True)
            st.plotly_chart(
                dual_radar_chart(data_a["competencies"], data_a["display_name"],
                                  data_b["competencies"], data_b["display_name"]),
                use_container_width=True, config={"displayModeBar": False},
            )
 
        st.write("")
        colA, colB = st.columns(2)
        for col, data in zip([colA, colB], [data_a, data_b]):
            score, matched, missing = ats_score(data["skills"], data["text"], st.session_state.job_description)
            with col:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;">{avatar(data["display_name"])}<h3 style="margin:0;">{data["display_name"]}</h3></div>',
                        unsafe_allow_html=True,
                    )
                    mm1, mm2 = st.columns(2)
                    mm1.metric("Experience", f"{data['exp_years']} yrs" if data["exp_years"] else "Not stated")
                    mm2.metric("ATS Score", f"{score}%" if st.session_state.job_description else "—")
                    st.progress(score / 100)
                    st.caption(f"🎓 {data['education']}")
                    st.markdown("**Skills**")
                    if data["skills"]:
                        st.markdown(
                            " ".join([f'<span class="pill pill-purple">{s}</span>' for s in data["skills"]]),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption("No taxonomy skills detected.")
                    if st.session_state.job_description:
                        st.markdown("**Matching Keywords**")
                        st.markdown(
                            " ".join([f'<span class="pill pill-teal">{s}</span>' for s in matched]) or "_None_",
                            unsafe_allow_html=True,
                        )
 
# ==================================================================================
# FEATURE 7 — CANDIDATE RANKING
# ==================================================================================
elif feature == "🏆 Candidate Ranking":
    app_header("Candidate Ranking", "Leaderboard of all candidates ranked by JD match score", "🏆 Top Talent")
 
    if not st.session_state.candidates:
        empty_state("🏆", "No candidates yet", "Upload resumes to populate the leaderboard.")
    elif not st.session_state.job_description:
        empty_state("📋", "No job description set", "Add a job description so candidates can be scored and ranked.")
    else:
        rows = []
        for key, data in st.session_state.candidates.items():
            score, matched, missing = ats_score(data["skills"], data["text"], st.session_state.job_description)
            tag = "🟢 Strong Fit" if score >= 75 else ("🟡 Moderate Fit" if score >= 50 else "🔴 Weak Fit")
            rows.append({
                "Candidate": data["display_name"], "ATS Score (%)": score,
                "Experience (yrs)": data["exp_years"] if data["exp_years"] else "—",
                "Matched Skills": len(matched), "Missing Skills": len(missing), "Fit Tag": tag,
            })
 
        df = pd.DataFrame(rows).sort_values("ATS Score (%)", ascending=False).reset_index(drop=True)
        df.insert(0, "Rank", range(1, len(df) + 1))
 
        st.markdown('<p class="section-title">🥇 Top Performers</p>', unsafe_allow_html=True)
        top_cols = st.columns(min(3, len(df)))
        medals = ["🥇", "🥈", "🥉"]
        for i, col in enumerate(top_cols):
            if i < len(df):
                row = df.iloc[i]
                with col:
                    with st.container(border=True):
                        st.markdown(f"<div style='text-align:center;'>{avatar(row['Candidate'], 46)}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align:center; font-size:1.6rem; margin-top:4px;'>{medals[i]}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align:center; font-weight:700;'>{row['Candidate']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align:center; font-size:1.5rem; font-weight:800; color:#5eead4;'>{row['ATS Score (%)']}%</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align:center;'>{row['Fit Tag']}</div>", unsafe_allow_html=True)
 
        st.write("")
        with st.container(border=True):
            st.markdown('<p class="section-title">📊 Score Distribution</p>', unsafe_allow_html=True)
            chart_df = df.copy()
            chart_df["ATS Score (%)"] = pd.to_numeric(chart_df["ATS Score (%)"], errors="coerce").fillna(0)
            st.plotly_chart(ranking_bar_chart(chart_df), use_container_width=True, config={"displayModeBar": False})
 
        st.write("")
        with st.container(border=True):
            st.markdown('<p class="section-title">📋 Full Leaderboard</p>', unsafe_allow_html=True)
            st.dataframe(
                df, use_container_width=True, hide_index=True,
                column_config={
                    "ATS Score (%)": st.column_config.ProgressColumn("ATS Score (%)", min_value=0, max_value=100, format="%d%%"),
                },
            )
            st.download_button(
                "⬇️ Download Ranking as CSV", df.to_csv(index=False).encode("utf-8"),
                file_name="candidate_ranking.csv", mime="text/csv",
            )
 
'''
import os
import re
import hashlib
from io import BytesIO
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pypdf import PdfReader
import docx
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
# ============================================================
# RAG BACKEND
# ============================================================
try:
    from rag_backend import (
    index_resume,
    ask_resume_question,
    retrieve_resume_chunks,
    check_rag_connection,)
    RAG_BACKEND_AVAILABLE = True
    RAG_BACKEND_ERROR = None
except Exception as e:
    RAG_BACKEND_AVAILABLE = False
    RAG_BACKEND_ERROR = str(e)
# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Resume Intelligence Pro",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main {
        background-color: #f7f9fc;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    .hero {
        background: linear-gradient(
            135deg,
            #111827 0%,
            #1e3a8a 50%,
            #2563eb 100%
        );
        padding: 28px;
        border-radius: 18px;
        color: white;
        margin-bottom: 25px;
    }

    .hero h1 {
        font-size: 38px;
        margin-bottom: 5px;
    }

    .hero p {
        font-size: 16px;
        opacity: 0.9;
    }

    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 3px 12px rgba(0,0,0,0.04);
        text-align: center;
    }

    .metric-value {
        font-size: 30px;
        font-weight: 700;
        color: #2563eb;
    }

    .metric-label {
        color: #6b7280;
        font-size: 14px;
    }

    .skill {
        display: inline-block;
        background: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
        padding: 5px 10px;
        border-radius: 20px;
        margin: 3px;
        font-size: 13px;
    }

    .matched-skill {
        display: inline-block;
        background: #ecfdf5;
        color: #047857;
        border: 1px solid #a7f3d0;
        padding: 5px 10px;
        border-radius: 20px;
        margin: 3px;
        font-size: 13px;
    }

    .missing-skill {
        display: inline-block;
        background: #fef2f2;
        color: #b91c1c;
        border: 1px solid #fecaca;
        padding: 5px 10px;
        border-radius: 20px;
        margin: 3px;
        font-size: 13px;
    }

    .info-box {
        background: #eff6ff;
        border-left: 5px solid #2563eb;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }

    .warning-box {
        background: #fffbeb;
        border-left: 5px solid #f59e0b;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }

    .success-box {
        background: #ecfdf5;
        border-left: 5px solid #10b981;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }

    .danger-box {
        background: #fef2f2;
        border-left: 5px solid #ef4444;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SKILL TAXONOMY
# ============================================================

SKILL_POOL = [
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "C",
    "C++",
    "C#",
    "Go",
    "Golang",
    "Rust",
    "PHP",
    "Ruby",
    "Kotlin",
    "Swift",
    "Scala",

    "HTML",
    "CSS",
    "React",
    "Angular",
    "Vue",
    "Node.js",
    "Express",
    "Next.js",
    "Django",
    "Flask",
    "FastAPI",
    "REST API",
    "GraphQL",

    "Machine Learning",
    "Deep Learning",
    "Artificial Intelligence",
    "Natural Language Processing",
    "NLP",
    "Computer Vision",
    "Generative AI",
    "LLM",
    "Large Language Models",
    "RAG",
    "Retrieval Augmented Generation",
    "LangChain",
    "LlamaIndex",
    "Hugging Face",
    "Transformers",
    "TensorFlow",
    "PyTorch",
    "Scikit-learn",
    "Pandas",
    "NumPy",
    "Matplotlib",
    "Seaborn",
    "Plotly",
    "OpenCV",

    "SQL",
    "MySQL",
    "PostgreSQL",
    "MongoDB",
    "SQLite",
    "Redis",
    "Oracle",
    "SQL Server",
    "Qdrant",
    "Pinecone",
    "FAISS",
    "Vector Database",

    "AWS",
    "Azure",
    "Google Cloud",
    "GCP",
    "Docker",
    "Kubernetes",
    "Jenkins",
    "CI/CD",
    "Git",
    "GitHub",
    "GitLab",

    "Power BI",
    "Tableau",
    "Excel",
    "Business Intelligence",
    "Data Analysis",
    "Data Visualization",
    "Statistics",

    "Project Management",
    "Agile",
    "Scrum",
    "JIRA",
    "Leadership",
    "Communication",
    "Problem Solving",
    "Stakeholder Management",
    "Product Management",
    "Marketing",
    "Digital Marketing",
]


# ============================================================
# STOPWORDS
# ============================================================

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from",
    "your", "you", "our", "are", "will", "have", "has",
    "had", "was", "were", "been", "being", "their",
    "they", "them", "into", "about", "using", "used",
    "use", "work", "working", "role", "candidate",
    "responsibilities", "responsibility", "requirements",
    "required", "preferred", "ability", "strong", "good",
    "excellent", "years", "year", "experience", "skills",
    "skill", "knowledge", "team", "teams", "job",
    "position", "company", "organization", "including",
    "such", "etc", "must", "should", "would", "could",
    "can", "may", "more", "other", "all", "any", "both",
    "within", "across", "through", "provide", "develop",
    "development", "build", "building", "support",
    "maintain", "maintaining", "ensure", "responsible",
    "looking", "seeking", "join", "based", "related",
}


# ============================================================
# SESSION STATE
# ============================================================

def init_state():

    defaults = {
        "candidates": {},
        "job_description": "",
        "chat_history": [],
        "chat_target": None,
        "last_uploaded_hash": None,
    }

    for key, value in defaults.items():

        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def normalize_term(term):

    term = normalize_text(term)

    aliases = {
        "golang": "go",
        "node js": "node.js",
        "nodejs": "node.js",
        "powerbi": "power bi",
        "machine-learning": "machine learning",
        "deep-learning": "deep learning",
        "artificial-intelligence": "artificial intelligence",
        "natural-language-processing":
            "natural language processing",
        "retrieval-augmented-generation":
            "retrieval augmented generation",
    }

    return aliases.get(term, term)


def unique_preserve_order(items):

    seen = set()
    output = []

    for item in items:

        key = normalize_term(item)

        if key and key not in seen:

            seen.add(key)
            output.append(item)

    return output


def file_content_hash(uploaded_file):

    return hashlib.sha256(
        uploaded_file.getvalue()
    ).hexdigest()[:16]


# ============================================================
# TERM MATCHING
# ============================================================

def make_term_pattern(term):

    if not term:
        return r"(?!x)x"

    escaped = re.escape(
        str(term).strip()
    )

    escaped = escaped.replace(
        r"\ ",
        r"[\s\-]+"
    )

    return rf"(?<!\w){escaped}(?!\w)"


def term_exists(term, text):

    if not term or not text:
        return False

    return re.search(
        make_term_pattern(term),
        text,
        flags=re.IGNORECASE
    ) is not None


# ============================================================
# PDF / DOCX EXTRACTION
# ============================================================

def extract_pdf_text_pypdf(file_bytes):

    text_parts = []

    reader = PdfReader(
        BytesIO(file_bytes)
    )

    for page in reader.pages:

        try:

            page_text = (
                page.extract_text()
                or ""
            )

            text_parts.append(
                page_text
            )

        except Exception:
            continue

    return "\n".join(
        text_parts
    ).strip()


def extract_pdf_text_pdfplumber(file_bytes):

    if not PDFPLUMBER_AVAILABLE:
        return ""

    text_parts = []

    try:

        with pdfplumber.open(
            BytesIO(file_bytes)
        ) as pdf:

            for page in pdf.pages:

                page_text = (
                    page.extract_text()
                    or ""
                )

                text_parts.append(
                    page_text
                )

    except Exception:
        return ""

    return "\n".join(
        text_parts
    ).strip()


def extract_docx_text(file_bytes):

    try:

        document = docx.Document(
            BytesIO(file_bytes)
        )

        paragraphs = [
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        return "\n".join(
            paragraphs
        ).strip()

    except Exception:
        return ""


def extract_text(uploaded_file):

    file_name = uploaded_file.name.lower()
    file_bytes = uploaded_file.getvalue()

    if file_name.endswith(".pdf"):

        text = extract_pdf_text_pypdf(
            file_bytes
        )

        if len(text.strip()) < 50:

            fallback = (
                extract_pdf_text_pdfplumber(
                    file_bytes
                )
            )

            if len(fallback.strip()) > len(
                text.strip()
            ):

                text = fallback

        return text

    if file_name.endswith(".docx"):

        return extract_docx_text(
            file_bytes
        )

    if file_name.endswith(".txt"):

        return file_bytes.decode(
            "utf-8",
            errors="ignore"
        )

    return ""


# ============================================================
# RESUME ANALYSIS
# ============================================================

def detect_skills(text):

    if not text:
        return []

    detected = []

    for skill in SKILL_POOL:

        if term_exists(
            skill,
            text
        ):

            detected.append(
                skill
            )

    return unique_preserve_order(
        detected
    )


def extract_experience_years(text):

    if not text:
        return 0.0

    patterns = [
        r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience",
        r"experience\s*(?:of|:)?\s*(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)",
    ]

    values = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        for value in matches:

            try:
                values.append(
                    float(value)
                )

            except ValueError:
                pass

    if not values:
        return 0.0

    return max(values)


def extract_education(text):

    if not text:
        return "Not detected"

    education_patterns = [
        (
            r"\b(ph\.?d|doctorate)\b",
            "PhD"
        ),
        (
            r"\b(master(?:'s)?|m\.?tech|m\.?e|mca|mba|msc|m\.sc)\b",
            "Master's"
        ),
        (
            r"\b(bachelor(?:'s)?|b\.?tech|b\.?e|bca|bba|bsc|b\.sc)\b",
            "Bachelor's"
        ),
        (
            r"\b(diploma)\b",
            "Diploma"
        ),
    ]

    for pattern, label in education_patterns:

        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        ):

            return label

    return "Not detected"


def extract_competencies(text):

    skills = detect_skills(text)

    competency_keywords = [
        "leadership",
        "communication",
        "problem solving",
        "stakeholder management",
        "project management",
        "teamwork",
        "analytical",
        "critical thinking",
        "decision making",
    ]

    found = []

    for item in competency_keywords:

        if term_exists(
            item,
            text
        ):

            found.append(
                item.title()
            )

    return unique_preserve_order(
        skills + found
    )


# ============================================================
# JD TERM EXTRACTION
# ============================================================

def extract_tokens(text):

    return re.findall(
        r"[a-zA-Z][a-zA-Z0-9+#./-]*",
        normalize_text(text)
    )


def extract_required_terms(job_description):

    if not job_description:
        return []

    jd = normalize_text(
        job_description
    )

    terms = []

    # Known technical/business skills
    for skill in SKILL_POOL:

        if term_exists(
            skill,
            jd
        ):

            terms.append(
                skill
            )

    # Important individual terms
    tokens = extract_tokens(jd)

    for token in tokens:

        clean = token.strip(
            ".,;:()[]{}"
        )

        if len(clean) < 3:
            continue

        if clean in STOPWORDS:
            continue

        if clean.isdigit():
            continue

        if clean in {
            "email",
            "address",
            "location",
            "date",
            "salary",
            "resume",
            "cv",
        }:
            continue

        terms.append(
            clean
        )

    return unique_preserve_order(
        terms
    )[:120]


# ============================================================
# ATS SCORE
# ============================================================

def get_score_category(score):

    if score >= 85:
        return "Excellent Match"

    if score >= 70:
        return "Strong Match"

    if score >= 55:
        return "Moderate Match"

    if score >= 40:
        return "Weak Match"

    return "Low Match"


def calculate_term_match(
    resume_text,
    required_terms
):

    matched = []
    missing = []

    for term in required_terms:

        if term_exists(
            term,
            resume_text
        ):

            matched.append(
                term
            )

        else:

            missing.append(
                term
            )

    return matched, missing


def ats_score(
    resume_skills,
    resume_text,
    job_description
):
    """
    Main ATS intelligence function.

    70% -> overall JD term coverage
    30% -> skill coverage

    This function is now the central ATS scoring
    function used throughout the application.
    """

    if not resume_text or not job_description:

        return {
            "score": 0,
            "category": "No Match",
            "matched": [],
            "missing": [],
            "required_terms": [],
            "coverage": 0,
            "jd_skills": [],
            "resume_skills": resume_skills or [],
            "matched_skills": [],
            "skill_coverage": 0,
        }

    required_terms = (
        extract_required_terms(
            job_description
        )
    )

    if not required_terms:

        return {
            "score": 0,
            "category": "No JD Terms",
            "matched": [],
            "missing": [],
            "required_terms": [],
            "coverage": 0,
            "jd_skills": [],
            "resume_skills": resume_skills or [],
            "matched_skills": [],
            "skill_coverage": 0,
        }

    matched, missing = calculate_term_match(
        resume_text,
        required_terms
    )

    term_coverage = (
        len(matched)
        / len(required_terms)
    ) * 100

    # JD skills
    jd_skills = [
        skill
        for skill in SKILL_POOL
        if term_exists(
            skill,
            job_description
        )
    ]

    # Resume skills
    if resume_skills is None:
        resume_skills = detect_skills(
            resume_text
        )

    matched_skills = [
        skill
        for skill in jd_skills
        if skill in resume_skills
    ]

    if jd_skills:

        skill_coverage = (
            len(matched_skills)
            / len(jd_skills)
        ) * 100

    else:

        skill_coverage = term_coverage

    # Final ATS score
    if jd_skills:

        final_score = (
            term_coverage * 0.70
            + skill_coverage * 0.30
        )

    else:

        final_score = term_coverage

    final_score = max(
        0,
        min(
            100,
            round(final_score)
        )
    )

    return {
        "score": final_score,
        "category": get_score_category(
            final_score
        ),
        "matched": matched,
        "missing": missing,
        "required_terms": required_terms,
        "coverage": round(
            term_coverage,
            1
        ),
        "jd_skills": jd_skills,
        "resume_skills": resume_skills,
        "matched_skills": matched_skills,
        "skill_coverage": round(
            skill_coverage,
            1
        ),
    }


def calculate_dynamic_ats_score(
    resume_text,
    job_description
):
    """
    Compatibility wrapper.
    """

    resume_skills = detect_skills(
        resume_text
    )

    return ats_score(
        resume_skills=resume_skills,
        resume_text=resume_text,
        job_description=job_description,
    )


def dynamic_ats_score(
    resume_text,
    job_description
):

    result = calculate_dynamic_ats_score(
        resume_text,
        job_description
    )

    return result["score"]


# ============================================================
# JD / RESUME RAG MATCHING
# ============================================================

def lexical_resume_retrieval(
    resume_text,
    job_description,
    max_sentences=12
):

    if not resume_text:
        return ""

    terms = extract_required_terms(
        job_description
    )

    if not terms:
        return resume_text[:8000]

    sentences = re.split(
        r"(?<=[.!?])\s+|\n+",
        resume_text
    )

    scored = []

    for sentence in sentences:

        sentence = sentence.strip()

        if not sentence:
            continue

        score = 0

        for term in terms:

            if term_exists(
                term,
                sentence
            ):

                score += 1

        if score > 0:

            scored.append(
                (
                    score,
                    sentence
                )
            )

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    selected = [
        sentence
        for _, sentence in scored[
            :max_sentences
        ]
    ]

    if selected:
        return "\n".join(
            selected
        )

    return resume_text[:8000]


def retrieve_jd_relevant_resume_text(
    candidate_name,
    resume_text,
    job_description,
    k=50
):

    if RAG_BACKEND_AVAILABLE:

        try:

            query = (
                "Find resume information relevant "
                "to this job description. Identify "
                "matching skills, technologies, "
                "experience, education, projects "
                "and responsibilities.\n\n"
                f"Job Description:\n"
                f"{job_description}"
            )

            documents = retrieve_resume_chunks(
                question=query,
                candidate_name=candidate_name,
                k=k,
            )

            if documents:

                context = "\n\n".join(
                    doc.page_content
                    for doc in documents
                )

                if context.strip():
                    return context

        except Exception:
            pass

    return lexical_resume_retrieval(
        resume_text,
        job_description
    )


# ============================================================
# AI MATCH ANALYSIS
# ============================================================

def get_openrouter_key():

    return (
        os.getenv(
            "OPENROUTER_API_KEY"
        )
        or os.getenv(
            "OPENAI_API_KEY"
        )
        or ""
    ).strip()


def call_llm_match_analysis(
    candidate_name,
    job_description,
    resume_context,
    ats_result,
):

    api_key = get_openrouter_key()

    if not api_key:
        return None

    try:

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        matched = ats_result.get(
            "matched",
            []
        )

        missing = ats_result.get(
            "missing",
            []
        )

        prompt = f"""
You are an AI Hiring Assistant helping a recruiter evaluate a candidate.

Candidate:
{candidate_name}

Job Description:
{job_description}

Relevant Resume Information:
{resume_context}

Deterministic ATS Score:
{ats_result["score"]}/100

Matched Terms:
{", ".join(matched) if matched else "None"}

Missing Terms:
{", ".join(missing) if missing else "None"}

Produce a concise recruiter-focused analysis with these sections:

1. Overall Match
2. Strong Matches
3. Missing or Weak Areas
4. Relevant Experience
5. Interview Focus
6. Hiring Recommendation

Rules:
- Use ONLY information present in the resume context or job description.
- Never invent candidate experience.
- Never assume a skill from a similar skill.
- Clearly distinguish missing information from missing skills.
- Do not change the deterministic ATS score.
- Keep the answer professional and actionable.
"""

        response = client.chat.completions.create(
            model=os.getenv(
                "OPENROUTER_MODEL",
                "google/gemini-2.5-flash"
            ),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise recruitment "
                        "analysis assistant."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
            max_tokens=1000,
        )

        return (
            response
            .choices[0]
            .message
            .content
        )

    except Exception as e:

        return (
            "AI Match Analysis could not be generated.\n\n"
            f"Technical reason: {e}"
        )


# ============================================================
# CHAT FALLBACK
# ============================================================

def chat_answer(
    question,
    resume_text
):

    if not resume_text:

        return (
            "I couldn't find resume information "
            "for this candidate."
        )

    question_tokens = set(
        token.lower()
        for token in extract_tokens(
            question
        )
        if len(token) >= 3
    )

    sentences = re.split(
        r"(?<=[.!?])\s+|\n+",
        resume_text
    )

    relevant = []

    for sentence in sentences:

        sentence_tokens = set(
            token.lower()
            for token in extract_tokens(
                sentence
            )
        )

        overlap = len(
            question_tokens.intersection(
                sentence_tokens
            )
        )

        if overlap:

            relevant.append(
                (
                    overlap,
                    sentence.strip()
                )
            )

    relevant.sort(
        key=lambda x: x[0],
        reverse=True
    )

    selected = [
        sentence
        for _, sentence in relevant[:6]
    ]

    if not selected:

        return (
            "I couldn't find enough information "
            "in this resume to answer that question."
        )

    return "\n\n".join(
        selected
    )


# ============================================================
# SCORE GAUGE
# ============================================================

def render_score_gauge(score):

    if score >= 70:
        color = "#10b981"

    elif score >= 50:
        color = "#f59e0b"

    else:
        color = "#ef4444"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={
                "suffix": "%",
                "font": {
                    "size": 42
                },
            },
            gauge={
                "axis": {
                    "range": [
                        0,
                        100
                    ]
                },
                "bar": {
                    "color": color
                },
                "steps": [
                    {
                        "range": [
                            0,
                            40
                        ],
                        "color": "#fee2e2",
                    },
                    {
                        "range": [
                            40,
                            70
                        ],
                        "color": "#fef3c7",
                    },
                    {
                        "range": [
                            70,
                            100
                        ],
                        "color": "#dcfce7",
                    },
                ],
            },
        )
    )

    fig.update_layout(
        height=280,
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20,
        ),
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# ============================================================
# CANDIDATE HELPERS
# ============================================================

def candidate_display_name(
    candidate_key
):

    candidate = (
        st.session_state
        .candidates
        .get(
            candidate_key,
            {}
        )
    )

    return candidate.get(
        "display_name",
        candidate_key
    )


def candidate_summary(candidate):

    return {
        "Candidate": candidate.get(
            "display_name",
            "Unknown"
        ),
        "File": candidate.get(
            "file_name",
            ""
        ),
        "Experience": candidate.get(
            "exp_years",
            0
        ),
        "Education": candidate.get(
            "education",
            "Not detected"
        ),
        "Skills": len(
            candidate.get(
                "skills",
                []
            )
        ),
    }
# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🎯 Resume Intelligence"
    )

    st.caption(
        "AI Hiring Assistant"
    )

    page = st.radio(
        "Navigation",
        [
            "Dashboard",
            "Upload Resume",
            "Upload Job Description",
            "Chat with Resumes",
            "ATS Resume Matcher",
            "AI Match Analysis",
            "Resume Analyzer",
            "Candidate Comparison",
            "Candidate Ranking",
        ],
    )

    st.divider()

# ============================================================
# RAG CONNECTION BOX
# ============================================================

with st.sidebar.expander(
    "🔌 RAG Connection",
    expanded=False
):

    try:

        rag_status = check_rag_connection()

        if rag_status["connected"]:

            st.success(
                "🟢 RAG Connected"
            )

            st.caption(
                "Local Qdrant: Ready"
            )

            st.caption(
                "RAG Backend: Ready"
            )

        else:

            st.error(
                "🔴 RAG Not Connected"
            )

            st.caption(
                rag_status["message"]
            )

            st.caption(
                "Start the app normally. "
                "Do not run rag_backend.py separately."
            )

    except Exception as e:

        st.error(
            "🔴 RAG Not Connected"
        )

        st.caption(
            str(e)
        )

    st.metric(
        "Candidates",
        len(
            st.session_state.candidates
        )
    )


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>🎯 Resume Intelligence Pro</h1>
        <p>
            AI-powered resume analysis, ATS scoring,
            job matching and recruiter intelligence.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DASHBOARD
# ============================================================

if page == "Dashboard":

    st.subheader(
        "Recruiter Dashboard"
    )

    candidates = (
        st.session_state.candidates
    )

    total_candidates = len(
        candidates
    )

    if total_candidates == 0:

        st.info(
            "No resumes uploaded yet. "
            "Go to 'Upload Resume' to add candidates."
        )

    else:

        avg_experience = (
            sum(
                c.get(
                    "exp_years",
                    0
                )
                for c in candidates.values()
            )
            / total_candidates
        )

        total_skills = sum(
            len(
                c.get(
                    "skills",
                    []
                )
            )
            for c in candidates.values()
        )

        
        col1, col2, col3,  = st.columns(3)

        with col1:

            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value">
                        {total_candidates}
                    </div>
                    <div class="metric-label">
                        Candidates
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:

            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value">
                        {avg_experience:.1f}
                    </div>
                    <div class="metric-label">
                        Avg. Experience
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col3:

            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value">
                        {total_skills}
                    </div>
                    <div class="metric-label">
                        Skills Detected
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        

        st.divider()

        rows = []

        for key, candidate in candidates.items():

            row = candidate_summary(
                candidate
            )

            # ------------------------------------------------
            # ATS intelligence integrated into dashboard
            # ------------------------------------------------

            if (
                st.session_state.job_description
            ):

                ats_result = (
                    calculate_dynamic_ats_score(
                        candidate["text"],
                        st.session_state.job_description,
                    )
                )

                row["ATS Score"] = (
                    f'{ats_result["score"]}%'
                )

                row["ATS Match"] = (
                    ats_result["category"]
                )

            else:

                row["ATS Score"] = "N/A"
                row["ATS Match"] = "JD Not Set"

            rows.append(row)

        df = pd.DataFrame(
            rows
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# UPLOAD RESUME
# ============================================================

elif page == "Upload Resume":

    st.subheader(
        "📄 Upload Resumes"
    )

    st.write(
        "Upload PDF or DOCX resumes. "
        "The application extracts the resume, "
        "detects skills and indexes it into local Qdrant."
    )

    uploaded_files = st.file_uploader(
        "Choose resume files",
        type=[
            "pdf",
            "docx"
        ],
        accept_multiple_files=True,
    )

    if uploaded_files:

        for uploaded_file in uploaded_files:

            content_hash = (
                file_content_hash(
                    uploaded_file
                )
            )

            base_name = os.path.splitext(
                uploaded_file.name
            )[0].strip()

            candidate_key = (
                f"{base_name} [{content_hash}]"
            )

            if (
                candidate_key
                in st.session_state.candidates
            ):

                st.info(
                    f"{uploaded_file.name} "
                    "is already uploaded."
                )

                continue

            # ------------------------------------------------
            # EXTRACT
            # ------------------------------------------------

            with st.spinner(
                f"Extracting {uploaded_file.name}..."
            ):

                text = extract_text(
                    uploaded_file
                )

            if not text.strip():

                st.error(
                    f"Could not extract text from "
                    f"{uploaded_file.name}."
                )

                continue

            # ------------------------------------------------
            # ANALYZE
            # ------------------------------------------------

            skills = detect_skills(
                text
            )

            exp_years = (
                extract_experience_years(
                    text
                )
            )

            education = (
                extract_education(
                    text
                )
            )

            competencies = (
                extract_competencies(
                    text
                )
            )

            # ------------------------------------------------
            # INDEX INTO QDRANT
            # ------------------------------------------------

            indexed_chunks = 0

            if RAG_BACKEND_AVAILABLE:

                try:

                    with st.spinner(
                        f"Creating RAG chunks for "
                        f"{uploaded_file.name}..."
                    ):

                        indexed_chunks = index_resume(
                            text=text,
                            candidate_name=base_name,
                            source=uploaded_file.name,
                        )

                    # Ensure we always have an integer.
                    if indexed_chunks is None:

                        indexed_chunks = 0

                    indexed_chunks = int(
                        indexed_chunks
                    )

                except Exception as e:

                    indexed_chunks = 0

                    st.error(
                        "Resume was extracted, "
                        "but Qdrant indexing failed."
                    )

                    st.code(
                        str(e)
                    )

            else:

                st.warning(
                    "RAG backend is not available. "
                    "Resume will be available for "
                    "non-RAG analysis only."
                )

            # ------------------------------------------------
            # SAVE CANDIDATE
            # ------------------------------------------------

            st.session_state.candidates[
                candidate_key
            ] = {

                "display_name": base_name,

                "file_name": uploaded_file.name,

                "text": text,

                "skills": skills,

                "exp_years": exp_years,

                "education": education,

                "competencies": competencies,

                # IMPORTANT:
                # Store the actual number returned
                # by rag_backend.index_resume()
                "indexed_chunks": indexed_chunks,

                "content_hash": content_hash,

                "uploaded_at":
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
            }

            # ------------------------------------------------
            # UPLOAD SUCCESS
            # ------------------------------------------------

            st.success(
                f"✅ {base_name} uploaded successfully."
            )

            

            # ------------------------------------------------
            # METRICS
            # ------------------------------------------------

            col1, col2, col3, col4 = st.columns(4)

            with col1:

                st.metric(
                    "Skills",
                    len(skills)
                )

            with col2:

                st.metric(
                    "Experience",
                    f"{exp_years:.1f} yrs"
                )

            with col3:

                st.metric(
                    "Education",
                    education
                )

            # ------------------------------------------------
            # ATS INTELLIGENCE
            # ------------------------------------------------

            if (
                st.session_state.job_description
            ):

                st.divider()

                ats_result = (
                    calculate_dynamic_ats_score(
                        resume_text=text,
                        job_description=
                            st.session_state.job_description,
                    )
                )

                st.subheader(
                    "🎯 Resume Intelligence Score"
                )

                ats_col1, ats_col2, ats_col3 = (
                    st.columns(3)
                )

                with ats_col1:

                    st.metric(
                        "ATS Score",
                        f'{ats_result["score"]}%'
                    )

                with ats_col2:

                    st.metric(
                        "JD Coverage",
                        f'{ats_result["coverage"]}%'
                    )

                with ats_col3:

                    st.metric(
                        "Skill Coverage",
                        f'{ats_result["skill_coverage"]}%'
                    )

                st.caption(
                    f'Match Level: '
                    f'{ats_result["category"]}'
                )

            # ------------------------------------------------
            # SKILLS
            # ------------------------------------------------

            with st.expander(
                f"Detected Skills — {base_name}"
            ):

                if skills:

                    st.markdown(
                        " ".join(
                            f'<span class="skill">'
                            f'{skill}'
                            f'</span>'
                            for skill in skills
                        ),
                        unsafe_allow_html=True,
                    )

                else:

                    st.caption(
                        "No predefined skills detected."
                    )


# ============================================================
# JOB DESCRIPTION
# ============================================================

elif page == "Upload Job Description":

    st.subheader(
        "💼 Job Description"
    )

    st.write(
        "Paste or upload the job description used "
        "for ATS scoring and candidate matching."
    )

    uploaded_jd = st.file_uploader(
        "Optional JD file",
        type=[
            "txt",
            "pdf",
            "docx"
        ],
        key="jd_upload",
    )

    if uploaded_jd:

        jd_text = extract_text(
            uploaded_jd
        )

        if not jd_text:

            if uploaded_jd.name.lower().endswith(
                ".txt"
            ):

                jd_text = (
                    uploaded_jd
                    .getvalue()
                    .decode(
                        "utf-8",
                        errors="ignore"
                    )
                )

        if jd_text:

            st.session_state.job_description = (
                jd_text
            )

            st.success(
                "Job description loaded."
            )

    jd_input = st.text_area(
        "Job Description",
        value=(
            st.session_state.job_description
        ),
        height=400,
        placeholder=(
            "Paste the complete job description here..."
        ),
    )

    if st.button(
        "💾 Save Job Description",
        type="primary",
        use_container_width=True,
    ):

        if not jd_input.strip():

            st.warning(
                "Please enter a job description."
            )

        else:

            st.session_state.job_description = (
                jd_input.strip()
            )

            st.success(
                "Job description saved."
            )

    if st.session_state.job_description:

        st.divider()

        terms = extract_required_terms(
            st.session_state.job_description
        )

        st.subheader(
            "Detected JD Requirements"
        )

        st.write(
            f"{len(terms)} meaningful terms detected."
        )

        st.markdown(
            " ".join(
                f'<span class="skill">'
                f'{term}'
                f'</span>'
                for term in terms
            ),
            unsafe_allow_html=True,
        )


# ============================================================
# CHAT WITH RESUMES
# ============================================================

elif page == "Chat with Resumes":

    st.subheader(
        "💬 Chat with Resumes"
    )

    candidates = (
        st.session_state.candidates
    )

    if not candidates:

        st.info(
            "Upload at least one resume first."
        )

    else:

        candidate = st.selectbox(
            "Select Candidate",
            list(candidates.keys()),
            format_func=candidate_display_name,
        )

        if (
            st.session_state.chat_target
            != candidate
        ):

            st.session_state.chat_history = []
            st.session_state.chat_target = candidate

        candidate_data = (
            candidates[candidate]
        )

        st.caption(
            f"Chatting with: "
            f"**{candidate_data['display_name']}**"
        )

        for message in (
            st.session_state.chat_history
        ):

            with st.chat_message(
                message["role"]
            ):

                st.markdown(
                    message["content"]
                )

        user_question = st.chat_input(
            "Ask something about this resume..."
        )

        if user_question:

            st.session_state.chat_history.append(
                {
                    "role": "user",
                    "content": user_question,
                }
            )

            with st.chat_message("user"):

                st.markdown(
                    user_question
                )

            with st.chat_message(
                "assistant"
            ):

                if RAG_BACKEND_AVAILABLE:

                    try:

                        reply = ask_resume_question(
                            question=user_question,
                            candidate_name=
                                candidate_data[
                                    "display_name"
                                ],
                        )

                    except Exception as e:

                        reply = (
                            "RAG could not answer "
                            "the question. "
                            "Using resume fallback.\n\n"
                            +
                            chat_answer(
                                user_question,
                                candidate_data[
                                    "text"
                                ],
                            )
                        )

                        st.caption(
                            f"RAG fallback: {e}"
                        )

                else:

                    reply = chat_answer(
                        user_question,
                        candidate_data[
                            "text"
                        ],
                    )

                st.markdown(
                    reply
                )

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": reply,
                }
            )


# ============================================================
# ATS RESUME MATCHER
# ============================================================

elif page == "ATS Resume Matcher":

    st.subheader(
        "📊 ATS Resume Matcher"
    )

    job_description = (
        st.session_state.job_description
    )

    candidates = (
        st.session_state.candidates
    )

    if not candidates:

        st.info(
            "Upload resumes before running ATS matching."
        )

    elif not job_description.strip():

        st.warning(
            "Please upload or save a job description first."
        )

    else:

        results = []

        for key, candidate in candidates.items():

            result = (
                calculate_dynamic_ats_score(
                    resume_text=
                        candidate["text"],
                    job_description=
                        job_description,
                )
            )

            results.append(
                {
                    "Candidate":
                        candidate[
                            "display_name"
                        ],
                    "ATS Score":
                        result[
                            "score"
                        ],
                    "Category":
                        result[
                            "category"
                        ],
                    "Matched Terms":
                        len(
                            result[
                                "matched"
                            ]
                        ),
                    "Missing Terms":
                        len(
                            result[
                                "missing"
                            ]
                        ),
                }
            )

        results_df = (
            pd.DataFrame(
                results
            )
            .sort_values(
                "ATS Score",
                ascending=False
            )
        )

        st.dataframe(
            results_df,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        selected_candidate = st.selectbox(
            "View Detailed ATS Result",
            list(candidates.keys()),
            format_func=candidate_display_name,
        )

        selected = candidates[
            selected_candidate
        ]

        result = (
            calculate_dynamic_ats_score(
                selected["text"],
                job_description,
            )
        )

        col1, col2 = st.columns(
            [1, 1]
        )

        with col1:

            render_score_gauge(
                result["score"]
            )

        with col2:

            st.markdown(
                f"### {result['category']}"
            )

            st.metric(
                "ATS Score",
                f'{result["score"]}%'
            )

            st.metric(
                "JD Term Coverage",
                f'{result["coverage"]}%'
            )

            st.metric(
                "Skill Coverage",
                f'{result["skill_coverage"]}%'
            )

        st.divider()

        col1, col2 = st.columns(2)

        with col1:

            st.subheader(
                "✅ Matched Requirements"
            )

            if result["matched"]:

                st.markdown(
                    " ".join(
                        f'<span class="matched-skill">'
                        f'{term}'
                        f'</span>'
                        for term in result[
                            "matched"
                        ]
                    ),
                    unsafe_allow_html=True,
                )

            else:

                st.info(
                    "No required terms were matched."
                )

        with col2:

            st.subheader(
                "❌ Missing Requirements"
            )

            if result["missing"]:

                st.markdown(
                    " ".join(
                        f'<span class="missing-skill">'
                        f'{term}'
                        f'</span>'
                        for term in result[
                            "missing"
                        ]
                    ),
                    unsafe_allow_html=True,
                )

            else:

                st.success(
                    "No missing requirements detected."
                )


# ============================================================
# AI MATCH ANALYSIS
# ============================================================

elif page == "AI Match Analysis":

    st.subheader(
        "🤖 AI Match Analysis"
    )

    candidates = (
        st.session_state.candidates
    )

    job_description = (
        st.session_state.job_description
    )

    if not candidates:

        st.info(
            "Upload resumes first."
        )

    elif not job_description.strip():

        st.warning(
            "Please save a job description first."
        )

    else:

        selected_candidate = st.selectbox(
            "Select Candidate",
            list(candidates.keys()),
            format_func=candidate_display_name,
        )

        candidate = candidates[
            selected_candidate
        ]

        with st.spinner(
            "Calculating ATS intelligence..."
        ):

            ats_result = (
                calculate_dynamic_ats_score(
                    resume_text=
                        candidate["text"],
                    job_description=
                        job_description,
                )
            )

        st.markdown(
            f"### {candidate['display_name']}"
        )

        col1, col2, col3, = st.columns(3)

        with col1:

            st.metric(
                "ATS Score",
                f'{ats_result["score"]}%'
            )

        with col2:

            st.metric(
                "JD Coverage",
                f'{ats_result["coverage"]}%'
            )

        with col3:

            st.metric(
                "Skill Coverage",
                f'{ats_result["skill_coverage"]}%'
            )

        st.caption(
            f"Match Level: "
            f"{ats_result['category']}"
        )

        st.divider()

        with st.spinner(
            "Finding resume information relevant to the JD..."
        ):

            relevant_context = (
                retrieve_jd_relevant_resume_text(
                    candidate_name=
                        candidate[
                            "display_name"
                        ],
                    resume_text=
                        candidate[
                            "text"
                        ],
                    job_description=
                        job_description,
                    k=50,
                )
            )

        with st.spinner(
            "Generating recruiter analysis..."
        ):

            ai_analysis = (
                call_llm_match_analysis(
                    candidate_name=
                        candidate[
                            "display_name"
                        ],
                    job_description=
                        job_description,
                    resume_context=
                        relevant_context,
                    ats_result=
                        ats_result,
                )
            )

        if ai_analysis:

            st.subheader(
                "AI Recruiter Analysis"
            )

            st.markdown(
                ai_analysis
            )

        else:

            st.info(
                "OpenRouter API key is not configured. "
                "Showing deterministic ATS analysis."
            )

            st.markdown(
                f"""
                <div class="info-box">
                    <strong>Overall Match:</strong>
                    {ats_result["category"]}
                    ({ats_result["score"]}%)
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.subheader(
                "Strong Matches"
            )

            if ats_result["matched"]:

                st.markdown(
                    " ".join(
                        f'<span class="matched-skill">'
                        f'{x}'
                        f'</span>'
                        for x in ats_result[
                            "matched"
                        ]
                    ),
                    unsafe_allow_html=True,
                )

            else:

                st.info(
                    "No strong requirement matches detected."
                )

            st.subheader(
                "Potential Gaps"
            )

            if ats_result["missing"]:

                st.markdown(
                    " ".join(
                        f'<span class="missing-skill">'
                        f'{x}'
                        f'</span>'
                        for x in ats_result[
                            "missing"
                        ]
                    ),
                    unsafe_allow_html=True,
                )

            else:

                st.success(
                    "No major requirement gaps detected."
                )

        st.divider()

        with st.expander(
            "View Resume Evidence Used"
        ):

            st.text(
                relevant_context
            )


# ============================================================
# RESUME ANALYZER
# ============================================================

elif page == "Resume Analyzer":

    st.subheader(
        "🔎 Resume Analyzer"
    )

    candidates = (
        st.session_state.candidates
    )

    if not candidates:

        st.info(
            "Upload resumes first."
        )

    else:

        selected_candidate = st.selectbox(
            "Select Candidate",
            list(candidates.keys()),
            format_func=candidate_display_name,
        )

        candidate = candidates[
            selected_candidate
        ]

        col1, col2, col3, = st.columns(3)

        with col1:

            st.metric(
                "Experience",
                f'{candidate["exp_years"]:.1f} yrs'
            )

        with col2:

            st.metric(
                "Skills",
                len(
                    candidate[
                        "skills"
                    ]
                )
            )

        with col3:

            st.metric(
                "Education",
                candidate[
                    "education"
                ]
            )

        # ----------------------------------------------------
        # ATS INTELLIGENCE
        # ----------------------------------------------------

        if st.session_state.job_description:

            st.divider()

            ats_result = (
                calculate_dynamic_ats_score(
                    candidate["text"],
                    st.session_state.job_description,
                )
            )

            st.subheader(
                "🎯 ATS Intelligence"
            )

            a, b, c = st.columns(3)

            with a:

                st.metric(
                    "ATS Score",
                    f'{ats_result["score"]}%'
                )

            with b:

                st.metric(
                    "JD Coverage",
                    f'{ats_result["coverage"]}%'
                )

            with c:

                st.metric(
                    "Skill Coverage",
                    f'{ats_result["skill_coverage"]}%'
                )

            st.caption(
                f"Match: "
                f"{ats_result['category']}"
            )

        st.divider()

        st.subheader(
            "Detected Skills"
        )

        if candidate["skills"]:

            st.markdown(
                " ".join(
                    f'<span class="skill">'
                    f'{skill}'
                    f'</span>'
                    for skill in candidate[
                        "skills"
                    ]
                ),
                unsafe_allow_html=True,
            )

        else:

            st.info(
                "No predefined skills detected."
            )

        st.subheader(
            "Competencies"
        )

        if candidate["competencies"]:

            st.markdown(
                " ".join(
                    f'<span class="skill">'
                    f'{item}'
                    f'</span>'
                    for item in candidate[
                        "competencies"
                    ]
                ),
                unsafe_allow_html=True,
            )

        else:

            st.info(
                "No competencies detected."
            )

        st.divider()

        st.subheader(
            "Resume Text"
        )

        st.text_area(
            "Extracted Content",
            candidate["text"],
            height=500,
            disabled=True,
        )


# ============================================================
# CANDIDATE COMPARISON
# ============================================================

elif page == "Candidate Comparison":

    st.subheader(
        "⚖️ Candidate Comparison"
    )

    candidates = (
        st.session_state.candidates
    )

    if len(candidates) < 2:

        st.info(
            "Upload at least two candidates "
            "to compare them."
        )

    else:

        selected = st.multiselect(
            "Select Candidates",
            list(candidates.keys()),
            default=list(
                candidates.keys()
            )[:2],
            format_func=candidate_display_name,
        )

        if selected:

            rows = []

            for key in selected:

                candidate = candidates[
                    key
                ]

                row = {
                    "Candidate":candidate["display_name"],
                    "Experience":
                        candidate[
                            "exp_years"
                        ],
                    "Education":
                        candidate[
                            "education"
                        ],
                    "Skills":
                        len(
                            candidate[
                                "skills"
                            ]
                        ),
                }
                if st.session_state.job_description:

                    ats_result = calculate_dynamic_ats_score(
                        candidate["text"],
                        st.session_state.job_description,
                    )

                    row["ATS Score"] = f'{ats_result["score"]}%'

                    row["ATS Match"] = ats_result["category"]

                else:

                    row["ATS Score"] = "N/A"

                    row["ATS Match"] = "JD Not Set"


# ============================================================
# CANDIDATE RANKING
# ============================================================

elif page == "Candidate Ranking":

    st.subheader(
        "🏆 Candidate Ranking"
    )

    candidates = (
        st.session_state.candidates
    )

    job_description = (
        st.session_state.job_description
    )

    if not candidates:

        st.info(
            "Upload resumes first."
        )

    elif not job_description.strip():

        st.warning(
            "Add a job description first."
        )

    else:

        ranking = []

        for key, candidate in candidates.items():

            ats_result = (
                calculate_dynamic_ats_score(
                    resume_text=
                        candidate["text"],
                    job_description=
                        job_description,
                )
            )

            ranking.append(
                {
                    "Candidate":
                        candidate[
                            "display_name"
                        ],
                    "ATS Score":
                        ats_result[
                            "score"
                        ],
                    "Match":
                        ats_result[
                            "category"
                        ],
                    "Experience":
                        candidate[
                            "exp_years"
                        ],
                    "Skills":
                        len(
                            candidate[
                                "skills"
                            ]
                        ),
                    "Matched Terms":
                        len(
                            ats_result[
                                "matched"
                            ]
                        ),
                    "Missing Terms":
                        len(
                            ats_result[
                                "missing"
                            ]
                        ),
                }
            )

        ranking_df = (
            pd.DataFrame(
                ranking
            )
            .sort_values(
                [
                    "ATS Score",
                    "Experience",
                ],
                ascending=False
            )
        )

        ranking_df.insert(
            0,
            "Rank",
            range(
                1,
                len(ranking_df) + 1
            ),
        )

        st.dataframe(
            ranking_df,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        if not ranking_df.empty:

            top_candidate = (
                ranking_df.iloc[0]
            )

            st.markdown(
                f"""
                <div class="success-box">
                    <strong>🏆 Top Candidate:</strong>
                    {top_candidate["Candidate"]}
                    <br>
                    ATS Score:
                    <strong>
                        {top_candidate["ATS Score"]}%
                    </strong>
                </div>
                """,
                unsafe_allow_html=True,
            )

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=ranking_df[
                    "Candidate"
                ],
                y=ranking_df[
                    "ATS Score"
                ],
                marker_color="#2563eb",
                text=ranking_df[
                    "ATS Score"
                ],
                textposition="auto",
            )
        )

        fig.update_layout(
            title="Candidate ATS Ranking",
            xaxis_title="Candidate",
            yaxis_title="ATS Score",
            yaxis=dict(
                range=[
                    0,
                    100
                ]
            ),
            height=450,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption("Resume Intelligence Pro•")