import re
import io
import time
import requests
import threading
import pdfplumber
from firebase_admin import firestore
from firebase_config import db

# Lock and flag to prevent multiple background workers from running concurrently
_lock = threading.Lock()
_worker_running = False

def get_direct_drive_link(url):
    """
    Extracts the file ID from a Google Drive sharing URL and converts it into a
    direct download link: https://drive.google.com/uc?export=download&id=FILE_ID
    """
    if not isinstance(url, str):
        return None
        
    # Match standard file view links: drive.google.com/file/d/FILE_ID/view...
    match_d = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match_d:
        file_id = match_d.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
        
    # Match sharing links using open?id=FILE_ID
    match_open = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if match_open:
        file_id = match_open.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
        
    return url

def _parse_pdf_text(pdf_bytes):
    """
    Uses pdfplumber to extract text from raw PDF bytes.
    """
    text_content = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_content += page_text + "\n"
    return text_content.strip()

def _resume_processing_worker():
    """
    Worker function executed in the background thread.
    Polls Firestore for candidates with status 'PENDING_RESUME',
    downloads their resume, saves it to Firebase Storage, extracts
    text, and updates Firestore.
    """
    global _worker_running
    
    try:
        if db is None:
            print("Firestore db client is not initialized. Worker stopping.")
            return

        while True:
            # Query candidates with PENDING_RESUME status (process in small batches)
            candidates_ref = db.collection("candidates")
            pending_docs = list(candidates_ref.where("status", "==", "PENDING_RESUME").limit(5).stream())
            
            if not pending_docs:
                break  # No more pending candidates, exit the loop
                
            for doc in pending_docs:
                doc_id = doc.id
                candidate_data = doc.to_dict()
                email = candidate_data.get("email", "Unknown Email")
                resume_url = candidate_data.get("resume")
                
                if not resume_url:
                    db.collection("candidates").document(doc_id).update({
                        "status": "FAILED_RESUME",
                        "error_message": "Resume link is empty"
                    })
                    continue
                
                try:
                    direct_url = get_direct_drive_link(resume_url)
                    
                    # 1. Download Resume from direct link (with timeout)
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    response = requests.get(direct_url, headers=headers, timeout=20)
                    response.raise_for_status()
                    
                    pdf_bytes = response.content
                    
                    # 2. Load the raw bytes directly into memory and parse using pdfplumber
                    extracted_text = _parse_pdf_text(pdf_bytes)
                    
                    # 3. Update Firestore with extracted text and transition status
                    update_payload = {
                        "status": "RESUME_PARSED",
                        "resume_text": extracted_text,
                        "processed_at": firestore.SERVER_TIMESTAMP
                    }
                        
                    db.collection("candidates").document(doc_id).update(update_payload)
                    print(f"Successfully processed resume for: {email}")
                    
                except Exception as e:
                    # Log failure in candidate doc to avoid stuck states
                    db.collection("candidates").document(doc_id).update({
                        "status": "FAILED_RESUME",
                        "error_message": str(e),
                        "processed_at": firestore.SERVER_TIMESTAMP
                    })
                    print(f"Failed to process resume for {email}: {e}")
            
            # Short sleep between batches to respect rate limits
            time.sleep(1)
            
    finally:
        with _lock:
            _worker_running = False

def start_resume_processing():
    """
    Safely starts the resume processing background worker thread if it is not already running.
    """
    global _worker_running
    
    with _lock:
        if _worker_running:
            return False  # Already running
        _worker_running = True
        
    thread = threading.Thread(target=_resume_processing_worker, daemon=True)
    thread.start()
    return True

def process_resumes_synchronously():
    """
    Synchronously processes all pending resumes in Firestore.
    """
    if db is None:
        return 0, "Database connection not initialized."
        
    candidates_ref = db.collection("candidates")
    pending_docs = list(candidates_ref.where("status", "==", "PENDING_RESUME").stream())
    
    if not pending_docs:
        return 0, None
        
    import streamlit as st
    progress_placeholder = st.empty()
    processed_count = 0
    for idx, doc in enumerate(pending_docs):
        doc_id = doc.id
        candidate_data = doc.to_dict()
        email = candidate_data.get("email", "Unknown Email")
        name = candidate_data.get("name", "Candidate")
        resume_url = candidate_data.get("resume")
        
        progress_placeholder.info(f"Extracting resume for {name} ({idx+1}/{len(pending_docs)}) - Please wait, respecting API limits...")
        
        if not resume_url:
            db.collection("candidates").document(doc_id).update({
                "status": "FAILED_RESUME",
                "error_message": "Resume link is empty"
            })
            continue
            
        try:
            direct_url = get_direct_drive_link(resume_url)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(direct_url, headers=headers, timeout=20)
            response.raise_for_status()
            
            pdf_bytes = response.content
            extracted_text = _parse_pdf_text(pdf_bytes)
            
            update_payload = {
                "status": "RESUME_PARSED",
                "resume_text": extracted_text,
                "processed_at": firestore.SERVER_TIMESTAMP
            }
            db.collection("candidates").document(doc_id).update(update_payload)
            processed_count += 1
            
            # Proactively space out requests to prevent hitting limits
            time.sleep(4)
        except Exception as e:
            db.collection("candidates").document(doc_id).update({
                "status": "FAILED_RESUME",
                "error_message": str(e),
                "processed_at": firestore.SERVER_TIMESTAMP
            })
            
    progress_placeholder.empty()
    return processed_count, None
