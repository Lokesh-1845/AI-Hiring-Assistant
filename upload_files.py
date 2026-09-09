#STEP 1
import streamlit as st
from pathlib import Path
# Folder where uploaded resumes will be saved
RESUME_FOLDER = Path("data/resumes")
# Create the folder if it does not exist
RESUME_FOLDER.mkdir(parents=True, exist_ok=True)
st.title("Resume Upload")
st.write("Upload your resumes in PDF or Word format.")
# File uploader for multiple files
uploaded_files = st.file_uploader("Choose resumes",type=["pdf", "doc", "docx"],accept_multiple_files=True)
# Save the uploaded files
if uploaded_files:
    for uploaded_file in uploaded_files:
        file_path = RESUME_FOLDER / uploaded_file.name
        with open(file_path, "wb") as file:
            file.write(uploaded_file.getbuffer())
        st.success(f"File uploaded successfully: {uploaded_file.name}")
        st.write(f"Saved to: {file_path}")
        




        #OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
#if not OPENROUTER_API_KEY:
    #raise ValueError("OPENROUTER_API_KEY not found in .env file.")