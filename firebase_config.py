import os
import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Global database client
db = None

def init_firebase():
    """
    Initializes the Firebase Admin SDK from Streamlit secrets.
    """
    global db
    
    if not firebase_admin._apps:
        try:
            # Directly read firebase config dict from Streamlit secrets
            firebase_secrets = dict(st.secrets["firebase"])
            
            # Format the private key to handle newline characters properly
            if "private_key" in firebase_secrets:
                firebase_secrets["private_key"] = firebase_secrets["private_key"].replace("\\n", "\n")
                
            # Explicitly set the environment variable and pass projectId option
            os.environ["GOOGLE_CLOUD_PROJECT"] = firebase_secrets.get("project_id", "")
            cred = credentials.Certificate(firebase_secrets)
            firebase_admin.initialize_app(cred, {'projectId': firebase_secrets.get('project_id')})
        except Exception as e:
            # Fallback to local default / environment configuration
            try:
                firebase_admin.initialize_app()
            except Exception as ex:
                st.sidebar.warning(f"⚠️ Firebase credentials not configured or initialization failed: {e}")
                return None

    try:
        proj_id = None
        try:
            proj_id = dict(st.secrets["firebase"]).get("project_id")
        except Exception:
            pass
        db = firestore.client(project=proj_id)
        return db
    except Exception as e:
        st.sidebar.warning(f"⚠️ Firestore Database client could not be initialized: {e}")
        db = None
        return None

# Trigger initialization on module import
try:
    init_firebase()
except Exception as e:
    pass
