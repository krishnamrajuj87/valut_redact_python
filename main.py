from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import mimetypes
import os
from dotenv import load_dotenv
from utils.redaction import fetch_document, redact_pdf, RedactionRule as PDFRedactionRule
from utils.docx_redaction import redact_docx, RedactionRule as DocxRedactionRule
from utils.firebase import upload_file_to_firebase, fetch_document_by_id, fetch_template_by_id, fetch_rules_by_ids, save_redaction_response, update_document_status, fetch_redaction_response
from utils.gemini import find_text_to_redact

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class RedactRequest(BaseModel):
    document_id: str
    template_id: str
    user_id: str

class RedactWithPromptRequest(BaseModel):
    document_id: str
    user_id: str
    prompt: str

def extract_text_from_document(doc_bytes: bytes, ext: str) -> str:
    print("ext",ext)
    if ext == ".pdf":
        # Use fitz (PyMuPDF) to extract text from PDF
        import fitz
        doc = fitz.open(stream=doc_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    elif ext == ".docx":
        # Use python-docx to extract text from DOCX
        from docx import Document
        import io
        doc_stream = io.BytesIO(doc_bytes)
        doc = Document(doc_stream)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

@app.post("/redact-with-prompt")
async def redact_with_prompt(request: RedactWithPromptRequest):
    try:
        # Fetch the existing redaction response
        existing_response = fetch_redaction_response(request.document_id)
        redacted_url = existing_response.get("file_url")
        if not redacted_url:
            raise HTTPException(status_code=400, detail="No redacted document URL found in response")
        
        # Fetch the redacted document
        doc_bytes = fetch_document(redacted_url)
        url = redacted_url.split("?")[0].strip()
        ext = os.path.splitext(url)[1].lower()
        original_filename = os.path.basename(url)
        last_modified = original_filename.split("%2F")[-1]

        # Extract text from document
        text = extract_text_from_document(doc_bytes, ext)

        # Use Gemini to find text to redact
        matches = find_text_to_redact(text, request.prompt)

        # Create redaction rules from matches
        rules = []
        for i, match in enumerate(matches):
            rules.append({
                "type": "text",
                "value": match["text"],
                "name": f"AI Detected {match['type']}",
                "rule_id": f"ai_{i}",
                "is_ai_detected": True
            })

        # Redact document based on found matches
        if ext == ".pdf":
            pdf_rules = [PDFRedactionRule(r["type"], r["value"], r["name"], r["rule_id"], r["is_ai_detected"]) for r in rules]
            result = redact_pdf(doc_bytes, pdf_rules, "ai_prompt")
            file_bytes = result["redacted_pdf"]
            report = result["report"]
        elif ext in [".docx"]:
            docx_rules = [DocxRedactionRule(r["type"], r["value"], r["name"], r["rule_id"], r["is_ai_detected"]) for r in rules]
            result = redact_docx(doc_bytes, docx_rules, "ai_prompt")
            file_bytes = result["redacted_docx"]
            report = result["report"]
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

        # Upload redacted document
        upload_path = f"{request.user_id}/redacted/{original_filename}"
        file_url = upload_file_to_firebase(file_bytes, upload_path)

        # Get existing redactions and total count
        existing_redactions = existing_response.get("redactions", [])
        existing_total = existing_response.get("total_redactions", 0)

        # Update indices for new redactions
        new_redactions = report["redactions"]
        for i, redaction in enumerate(new_redactions, start=existing_total):
            redaction["index"] = i

        # Combine existing and new redactions
        combined_redactions = existing_redactions + new_redactions
        total_redactions = existing_total + report["total_redactions"]

        # Prepare response
        response = {
            "file_url": file_url,
            "original_text": report["before_text"],
            "redacted_text": report["after_text"],
            "total_redactions": total_redactions,
            "redactions": combined_redactions,
            "report": report,
            "user_id": request.user_id,
            "document_id": request.document_id,
            "doc_id": request.document_id,
            "original_url": existing_response.get("original_url"),
            "original_filename": original_filename,
            "last_modified": last_modified,
            "redacted_filename": original_filename.replace(ext, "_redacted" + ext),
            "prompt": request.prompt,
            "ai_detected_matches": matches,
            "total_previous_redactions": existing_total,
            "template_id": "ai_prompt"  # Add template_id for consistency
        }

        # Save response in Firestore
        save_redaction_response(response)
        # Update document status
        update_document_status(request.document_id, "redacted", file_url)
        return response

    except Exception as e:
        # Update document status to failed if there's an error
        update_document_status(request.document_id, "failed", None)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/redact")
async def redact_document(request: RedactRequest):
    try:
        # Fetch document and template from Firestore
        doc_data = fetch_document_by_id(request.document_id)
        template_data = fetch_template_by_id(request.template_id)
        rule_ids = template_data.get("ruleIds", [])
        rules_data = fetch_rules_by_ids(rule_ids)
        # Prepare rules for redaction
        rules = []
        for r in rules_data:
            print(r)
            rule_type = r.get("type")
            value = r.get("pattern") if rule_type != "spacy" else r.get("key")
            name = r.get("name", "Unnamed Rule")
            rule_id = r.get("id", "No ID")
            if rule_type and value:
                rules.append({"type": rule_type, "value": value, "name": name, "rule_id": rule_id, "is_ai_detected": False})
        # Fetch document from URL
        document_url = doc_data.get("url")
        if not document_url:
            raise HTTPException(status_code=400, detail="Document URL not found in Firestore document")
        doc_bytes = fetch_document(document_url)
        url = document_url.split("?")[0].strip()
        ext = os.path.splitext(url)[1].lower()
        original_filename = os.path.basename(url)
        last_modified = original_filename.split("%2F")[-1]
        print(last_modified)
        # Detect file type and redact
        if ext == ".pdf":
            pdf_rules = [PDFRedactionRule(r["type"], r["value"], r["name"], r["rule_id"], r["is_ai_detected"]) for r in rules]
            result = redact_pdf(doc_bytes, pdf_rules, request.template_id)
            file_bytes = result["redacted_pdf"]
            report = result["report"]
        elif ext in [".docx"]:
            docx_rules = [DocxRedactionRule(r["type"], r["value"], r["name"], r["rule_id"], r["is_ai_detected"]) for r in rules]
            result = redact_docx(doc_bytes, docx_rules, request.template_id)
            file_bytes = result["redacted_docx"]
            report = result["report"]
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
        # Upload to Firebase in user_id/redacted/original_filename
        upload_path = f"{request.user_id}/redacted/{original_filename}"
        file_url = upload_file_to_firebase(file_bytes, upload_path)
        doc_id = f"{request.document_id}_{request.template_id}"
        response = {
            "file_url": file_url,
            "original_text":report["before_text"],
            "redacted_text":report["after_text"],
            "total_redactions":report["total_redactions"],
            "redactions":report["redactions"],
            "report": report,
            "user_id": request.user_id,
            "template_id": request.template_id,
            "document_id": request.document_id,
            "doc_id": request.document_id,
            "original_url": document_url,
            "original_filename": original_filename,
            "last_modified": last_modified,
            "redacted_filename": original_filename.replace(ext, "_redacted" + ext)
        }
        # Save response in Firestore
        save_redaction_response(response)
        # Update document status to success
        update_document_status(request.document_id, "redacted",file_url)
        return response
    except Exception as e:
        # Update document status to failed if there's an error
        update_document_status(request.document_id, "failed", None)
        raise HTTPException(status_code=500, detail=str(e)) 