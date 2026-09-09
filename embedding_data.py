from pathlib import Path
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
def load_chunks(folder_path):
    folder = Path(folder_path)
    if not folder.exists():
        print(f"Folder does not exist: {folder_path}")
        return []
    documents = []
    for file_path in folder.glob("*.txt"):
        print(f"Found file: {file_path}")
        text = file_path.read_text(encoding="utf-8")
        if not text.strip():
            print(f"Skipping empty file: {file_path}")
            continue
        document = Document(page_content=text,metadata={"source": file_path.name})
        documents.append(document)
    return documents
# Load embedding model
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
# Load chunks
folder_path = "data/extracted_text"  # Replace with your actual folder path
print(f"Looking for .txt files in: {folder_path}")


'''chunks = load_chunks(folder_path)
print("Total chunks:", len(chunks))
# Create embeddings
if chunks:
    vectors = embeddings.embed_documents(
        [chunk.page_content for chunk in chunks]
    )
    print("Total vectors:", len(vectors))
    if vectors:
        print("Vector dimension:", len(vectors[0]))
        # Print vectors in groups of 10
        print("\nVector embeddings in groups of 10:")
        for i in range(0, len(vectors), 10):
            print(f"Vectors {i + 1} to {min(i + 10, len(vectors))}:")
            for j, vector in enumerate(vectors[i:i + 10], start=i + 1):
                print(f"Vector {j}: {vector}")
            print()  # Add a blank line for readability
else:
    print("No chunks to process.")'''






chunks = load_chunks(folder_path)
print("Total chunks:", len(chunks))
# Create embeddings
if chunks:
    vectors = embeddings.embed_documents(
        [chunk.page_content for chunk in chunks])
    print("Total vectors:", len(vectors))
    if vectors:
        print("Vector dimension:", len(vectors[0]))
else:
    print("No chunks to process.")
# After generating embeddings
print("\nGenerated Embeddings:")
for i, chunk in enumerate(chunks):
    # Extract the text content from the Document object
    text = chunk.page_content  # Extract the actual text from the Document
    embedding = embeddings.embed_query(text)  # Pass the text to embed_query
    print(f"Chunk {i + 1} Embedding: {embedding[:10]}...")  # Print the first 10 values for brevity
    print(f"Metadata: {chunk.metadata}")