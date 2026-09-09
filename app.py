from flask import Flask, request, jsonify, render_template
from pathlib import Path
from text_extract import extract_text_from_pdf

app = Flask(__name__)

UPLOAD_FOLDER = Path("data/resumes")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


@app.route("/")
def home():
    return render_template("hiring_dashboard.html")


@app.route("/upload-resume", methods=["POST"])
def upload_resume():

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    # Save uploaded PDF
    pdf_path = UPLOAD_FOLDER / file.filename
    file.save(pdf_path)

    # Extract text using text_extract.py
    extracted_text = extract_text_from_pdf(str(pdf_path))

    return jsonify({
        "filename": file.filename,
        "text": extracted_text
    })


if __name__ == "__main__":
    app.run(debug=True)