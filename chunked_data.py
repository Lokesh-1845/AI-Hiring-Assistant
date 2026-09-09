from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
def load_resumes(folder_path: str):
    """
    Load all .txt resume files from a folder.
    """
    folder = Path(folder_path)
    documents = []
    for file_path in folder.glob("*.txt"):
        text = file_path.read_text(encoding="utf-8")
        if not text.strip():
            print(f"Skipping empty file: {file_path.name}")
            continue
        document = Document(
            page_content=text,
            metadata={
                "source": file_path.name,
                "candidate_id": file_path.stem})
        documents.append(document)
        print(f"Loaded: {file_path.name}")
    return documents
def create_chunks(documents):
    """
    Split resume documents into smaller chunks.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            ""])
    chunks = text_splitter.split_documents(documents)
    return chunks
if __name__ == "__main__":
    input_folder = "data/extracted_text"
    # Step 1: Load resumes
    documents = load_resumes(input_folder)
    print(f"\nTotal resumes loaded: "f"{len(documents)}")
    # Step 2: Create chunks
    chunks = create_chunks(documents)
    print(f"Total chunks created: "f"{len(chunks)}")
    # Step 3: Display chunks
    print("\n chunked data:")
    for i, chunk in enumerate(chunks):
        print("\n" + "=" * 70)
        print(f"CHUNK {i + 1}")
        print("-" * 70)
        print("Metadata:")
        print(chunk.metadata)
        print("\nContent:")
        print(chunk.page_content)





