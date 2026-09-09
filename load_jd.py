'''from pathlib import Path
def load_job_description(file_path):
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Job description not found: {path}")
    with open(path, "r", encoding="utf-8") as file:
        text = file.read()
    if not text.strip():
        raise ValueError("Job description is empty.")
    return text
BASE_DIR = Path(__file__).resolve().parent
job_description_path = (BASE_DIR/ "data"/ "job_description"/ "python_developer.txt")
print("Looking for file:")
print(job_description_path)
print("Exists:", job_description_path.exists())
job_description = load_job_description(job_description_path)
print("\nJD loaded successfully!")
print("=" * 60)
print(job_description)'''

from pathlib import Path
from langchain_core.documents import Document
def load_job_description(file_path):
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(
            f"Job description not found: {file_path}")
    text = file_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Job description is empty.")
    return Document(
        page_content=text,
        metadata={"source": file_path.name,"type": "job_description"})
job_description = load_job_description("data/job_description/python_developer.txt")
print("\nJD loaded successfully!")
print("=" * 60)
print(job_description.page_content)