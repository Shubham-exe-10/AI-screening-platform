import os
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

@st.cache_resource
def get_firestore_client():
    # 1. Load secrets
    firebase_secrets = dict(st.secrets["firebase"])
    
    # 2. Force environment variable
    project_id = firebase_secrets.get("project_id")
    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        
    # Format the private key to handle newline characters properly
    if "private_key" in firebase_secrets:
        firebase_secrets["private_key"] = firebase_secrets["private_key"].replace("\\n", "\n")
        
    # 3. Clear any zombie instances just in case
    if firebase_admin._apps:
        for app in list(firebase_admin._apps.keys()):
            firebase_admin.delete_app(firebase_admin.get_app(app))
            
    # 4. Initialize fresh
    cred = credentials.Certificate(firebase_secrets)
    firebase_admin.initialize_app(cred, {
        'projectId': project_id
    })
    
    return firestore.client()

# Call the cached function to get the database client
try:
    db = get_firestore_client()
except Exception as e:
    st.sidebar.warning(f"⚠️ Firebase initialization failed: {e}")
    db = None

def init_firebase():
    """
    Compatibility wrapper returning the database client.
    """
    global db
    if db is None:
        try:
            db = get_firestore_client()
        except Exception:
            pass
    return db
