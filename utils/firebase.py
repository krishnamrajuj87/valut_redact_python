import os
import mimetypes
from datetime import datetime
from fastapi import HTTPException
import firebase_admin
from firebase_admin import credentials, storage, firestore
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Firebase credentials from environment variables
FIREBASE_BUCKET = os.getenv("FIREBASE_BUCKET")
print("FIREBASE_BUCKET",FIREBASE_BUCKET)
PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCYrRfldbYBveVk\nU6LI+P7FT5muP2xdNTnN2Zt8g0bsQ5xSbdLIj5gs5G9qdK1dN+RcLwzv49rEeadL\nEQaleuav8gvmImsVr2f/ITfbLhCnjCeGuxkpNZWx/3VyZQaO2RF7j2x0owSl4ghV\n6Qn554nEZ3EEKeCyxc32DnWeQNPHqalVEWI7nxoLzV4wKTNZLZyo2AIlsSp8fs8c\ntttYXWohtaV0D6Izh9tVCwnB6u/Bmav+MNGySSfNksuMjeoqJTBoztU17tavFYpZ\nVKI2Omr+T8PCLLSqg9Ihhh+Ak2yVjXZ2AOKPSYg/FI+b05lOU8IDQZosAUzSlTIG\n/XPQFLaZAgMBAAECggEACqRF/iBuR0DNNGj/97IjT+10cMjK7NRA6zA3vj4IO3+a\n7cPp5UDdAoQJoAnx64VxzVsaM75WCUvRdVICfJZMbgcY/Tl47VIElavjEMvtLUB/\noMx5vH2XqYh8zzRreJl4tnwQuzCBqm5O1m4f2+Nfnuj236trlgpjiLsJR7aNDGWT\nWvLmdk8HHEkS50zLrSNf3QYxS7ycg2ufEWS4NPBsZRJY8/phw/jTTzyC/DytzVek\ndOjjIGt4zEkLAiNcJw/0ljPehnUizuLE5NMKZNL3nHPMu/WcUpHG51CtXpvAhUC1\nQSsnAS/+kFmSEgu8pZMRkdocrVc9K3/f+fp0dp34YQKBgQDVyRvcwBNoc59gLBxp\ney8KoeqHgUeDtV3n0n6SUBeMrtMpNFVHR5hPlj2IzPknfKhgNyuOpQMgktU8IOO3\nWP8Htm/BN7earD6Q+1/yUb7yZEkErDFFd/AFmNo0i9bMgQqaPs0u/sVGbUMWFY6/\nJ6AQvEMxfmfg3Wda312U3aEIwwKBgQC20uTamUbLaYrX4uPSubt87tOR2Pw+UE/W\n3mgq5pzEe3k8rdTu9v+566V6MJeNbIoT7bnwfBdVQOn8MCCnsm6VvuY176nwBFIO\nA2VDZxiWrDeMb/diL4uld6iEU7ijnEnH73ICrUQosYfP2chJtqJBXacQ1brn/k+4\nHZ/1TcatcwKBgQCG1lQrdD4JeDuCVfAJm3c9FoistJ5ddOvohjvsnnVr9uwaJfbP\ngVmQgOsIuHdBL3+nR8TCMFN7nQC+7uORRaF8xNVRoYm9FXxUxydp16M+kH/5YX2m\nGhKaBSFDWRu+WnlMdeXGCUx1sf5JFIm3CRAM3iDnO5nbGunQR+dnOC4ULwKBgFyR\ndbzVRQoze1CKGi6VSkAcsNU1F6r5gSNbY0TtlUzK8/zsS1dfiuX5UcUHm4TJAzTJ\n9o60ViAdiRvexnoCl4mMqgV/Pv0/QsjDoV86cTHBKzMZchmt1zhF2PZ/aYq11Im+\nTGzcjBlKomh0bbwdFBSitbeJcGSM2JJxtY8//SvPAoGAJrDRnlosQhoaOTTs9GAg\nK8veKbFoNQ+nCRjiKBRUB30EqPl/x8EFUO2nu0wE+bzf3gMgTobqBWPeyahOZFt0\nbPJplD/2RR/YbZgbkgaNxLxIENQs26OWqWOBJu+4IqgjPGUtJsbVb8eH5BOgcTmT\n2qT/z3Q5aOwvzSpXCZLXqcA=\n-----END PRIVATE KEY-----\n"
print("PRIVATE_KEY",PRIVATE_KEY)
PRIVATE_KEY_ID = os.getenv("PRIVATE_KEY_ID")
print("PRIVATE_KEY_ID",PRIVATE_KEY_ID)

FIREBASE_CREDENTIALS = {
    "type": "service_account",
    "project_id": os.getenv("PROJECT_ID"),
    "private_key_id": os.getenv("PRIVATE_KEY_ID"),
    "private_key": PRIVATE_KEY,
    "client_email": os.getenv("CLIENT_EMAIL"),
    "client_id": os.getenv("CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL"),
    "universe_domain": "googleapis.com"
}

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS)
    firebase_admin.initialize_app(cred, {
        'storageBucket': FIREBASE_BUCKET
    })

def upload_file_to_firebase(file_bytes: bytes, filename: str) -> str:
    bucket = storage.bucket()
    blob = bucket.blob(filename)
    # Guess content type
    content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        # Fallbacks for common types
        if filename.endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename.endswith('.docx'):
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            content_type = 'application/octet-stream'
    blob.upload_from_string(file_bytes, content_type=content_type)
    blob.make_public()
    return blob.public_url

def get_firestore_client():
    return firestore.client()

def fetch_document_by_id(document_id: str) -> dict:
    db = get_firestore_client()
    doc_ref = db.collection('documents').document(document_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise ValueError(f"Document with id {document_id} not found")
    return doc.to_dict()

def fetch_template_by_id(template_id: str) -> dict:
    db = get_firestore_client()
    template_ref = db.collection('templates').document(template_id)
    template = template_ref.get()
    if not template.exists:
        raise ValueError(f"Template with id {template_id} not found")
    return template.to_dict()

def fetch_rules_by_ids(rule_ids: list) -> list:
    db = get_firestore_client()
    rules = []
    remaining_rule_ids = rule_ids.copy()
    
    # First check redaction_rules
    for rule_id in rule_ids:
        rule_ref = db.collection('redaction_rules').document(rule_id)
        rule = rule_ref.get()
        if rule.exists:
            rule_data = rule.to_dict()
            rule_data["id"] = rule_id
            rules.append(rule_data)
            remaining_rule_ids.remove(rule_id)
    
    # Then check standard_rules only for remaining IDs
    for rule_id in remaining_rule_ids:
        rule_ref = db.collection('standard_rules').document(rule_id)
        rule = rule_ref.get()
        if rule.exists:
            rule_data = rule.to_dict()
            rule_data["id"] = rule_id
            rules.append(rule_data)
            
    return rules

def save_redaction_response(response: dict) -> None:
    db = get_firestore_client()
    doc_id = f"{response['document_id']}_{response['template_id']}"
    doc_ref = db.collection('redaction_responses').document(response['doc_id'])
    doc_ref.set(response)

def update_document_status(document_id: str, status: str, file_url: str | None = None)  -> None:
    db = get_firestore_client()
    doc_ref = db.collection('documents').document(document_id)
    doc_ref.update({
        'status': status,
        'updated_at': datetime.now(),
        'redactedUrl': file_url
    })

def fetch_redaction_response(document_id: str) -> dict:
    db = get_firestore_client()
    print("document_id",document_id)
    # Search for the most recent redaction response for this document
    template_ref = db.collection('redaction_responses').document(document_id)
    template = template_ref.get()
    if not template.exists:
        raise ValueError(f"Template with id {template_id} not found")
    return template.to_dict()