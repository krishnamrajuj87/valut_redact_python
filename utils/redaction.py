import fitz  # PyMuPDF
import requests
import re
from typing import List, Dict, Any
from utils.ner import NERProcessor

# Initialize NER processor
ner_processor = NERProcessor()

class RedactionRule:
    def __init__(self, type_: str, value: str, name: str, rule_id: str, is_ai_detected: bool):
        self.type = type_
        self.value = value
        self.name = name
        self.rule_id = rule_id
        self.is_ai_detected = is_ai_detected

def fetch_document(url: str) -> bytes:
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def getSpacyText(text, value):
    """
    Extract entities from text using NER processor.
    
    Args:
        text (str): The text to process
        value (str or list): The entity type(s) to extract
        
    Returns:
        list: List of extracted entities
    """
    try:
        entities = ner_processor.extract_entities(text)
        # Filter entities by type if specified
        if value:
            # Convert single value to list for consistent handling
            entity_types = [value] if isinstance(value, str) else value
            # Filter entities by any of the specified types
            entities = [ent for ent in entities if ent['type'].lower() in [t.lower() for t in entity_types]]
        return [ent['text'] for ent in entities]
    except Exception as e:
        print(f"Error in getSpacyText: {e}")
        return []

def redact_pdf(document_bytes: bytes, rules: List[RedactionRule], template_id: str) -> Dict[str, Any]:
    doc = fitz.open(stream=document_bytes, filetype="pdf")
    report = {"redactions": [], "template_id": template_id}
    total_redactions = 0
    # Extract initial text for before_text
    initial_text = ""
    for page_num in range(len(doc)):
        initial_text += doc[page_num].get_text("text")
    report["before_text"] = initial_text
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_report = []
        text = page.get_text("text")
        for rule in rules:
            print("rule",rule.type,rule.value)
            if rule.type == 'text':
                matches = [(m.start(), m.end(), m.group()) for m in re.finditer(re.escape(rule.value), text)]
            elif rule.type == 'regex':
                matches = [(m.start(), m.end(), m.group()) for m in re.finditer(rule.value, text)]
            elif rule.type == 'spacy':
                matches = []
                # Get all matching entities
                entities = getSpacyText(initial_text, rule.value)
                # Create matches for each entity
                for entity in entities:
                    # Find all occurrences of this entity in the text
                    entity_matches = [(m.start(), m.end(), m.group()) for m in re.finditer(re.escape(entity), text)]
                    matches.extend(entity_matches)
            else:
                continue
            for start, end, match_text in matches:
                areas = page.search_for(match_text)
                for rect in areas:
                    print(rect,match_text)
                    hover_text = f"Rule: {rule.name} (type: {rule.type})"
                    annot = page.add_redact_annot(rect, fill=(0, 0, 0))
                    annot.set_info("title", hover_text)
                    page.add_highlight_annot(rect)
                    page_report.append({
                        "rule": rule.name,
                        "type": rule.type,
                        "text": match_text,
                        "page": page_num + 1,
                        "rule_id": rule.rule_id,
                        "index":total_redactions,
                        "is_ai_detected": rule.is_ai_detected
                    })
                    total_redactions += 1
        if page_report:
            report["redactions"].extend(page_report)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    pdf_bytes = doc.write()
    # Extract final text for after_text
    final_text = ""
    doc_final = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num in range(len(doc_final)):
        final_text += doc_final[page_num].get_text("text")
    report["after_text"] = final_text
    # Format before_text in markdown with yellow background highlights
    before_text_md = initial_text
    for redaction in report["redactions"]:
        before_text_md = before_text_md.replace(redaction["text"], f"<span style='background-color: yellow;'>{redaction['text']}</span>")
    report["before_text"] = before_text_md
    report["total_redactions"] = total_redactions
    return {"redacted_pdf": pdf_bytes, "report": report} 