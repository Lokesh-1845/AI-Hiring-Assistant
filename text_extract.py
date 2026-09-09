#STEP -2
import pymupdf
from pathlib import Path
def extract_text_from_pdf(pdf_path: str) -> str:
    #Extract text from a single PDF using PyMuPDF.
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path}")
    extracted_text = []
    try:
        with pymupdf.open(str(pdf_path)) as document:
            print(f"\nFile: {pdf_path.name}")
            print(f"Number of pages: {len(document)}")
            for page_number, page in enumerate(document, start=1):
                page_text = page.get_text("text")
                if page_text.strip():
                    extracted_text.append(page_text)
                    print(f"Page {page_number}: "f"{len(page_text)} characters extracted")
                else:
                    print(f"Page {page_number}: ""No text found")
    except Exception as e:
        print(f"Error reading {pdf_path.name}: {e}")
        return ""
    # Combine all pages
    final_text = "\n\n".join(extracted_text)
    return final_text.strip()
def extract_text_from_multiple_pdfs(folder_path: str) -> dict:
#Extract text from all PDF files in a folder.
    folder_path = Path(folder_path)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    if not folder_path.is_dir():
        raise ValueError(f"Provided path is not a folder: {folder_path}")
    extracted_texts = {}
    pdf_files = list(folder_path.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found.")
        return extracted_texts
    for pdf_file in pdf_files:
        print("\n" + "=" * 60)
        print(f"Processing: {pdf_file.name}")
        print("=" * 60)
        text = extract_text_from_pdf(str(pdf_file))
        extracted_texts[pdf_file.name] = text
        if text:
            print(
                f"Successfully extracted "
                f"{len(text)} characters.")
        else:
            print(
                "WARNING: No text was extracted. "
                "This PDF may be image/scanned based.")
    return extracted_texts
def save_extracted_text(text: str,output_path: str) -> None:
    #Save extracted text into a TXT file.
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text(text,encoding="utf-8")
    print(f"Saved: {output_path}")
# MAIN
if __name__ == "__main__":
    input_folder = Path("data/resumes")
    output_folder = Path("data/extracted_text")
    if not input_folder.exists():
        print(
            f"Input folder does not exist: "
            f"{input_folder}")
    else:
        resumes = extract_text_from_multiple_pdfs(str(input_folder))
        for filename, text in resumes.items():
            print("\n" + "=" * 60)
            print(f"EXTRACTED TEXT: {filename}")
            print("=" * 60)
            if text:
                # Print first 2000 characters
                print(text[:5000])
                # Create output filename
                output_file = (
                    output_folder /
                    f"{Path(filename).stem}.txt")

                # Save text
                save_extracted_text(text,str(output_file))
            else:
                print("No text extracted from this PDF.")
        print("\nProcessing completed.")
        print(" all extracted text files are saved in the data/extracted_text folder.")
        # After extracting text from resumes
        # Replace `extracted_text` with the variable holding the extracted text





