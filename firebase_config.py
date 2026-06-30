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
    Initializes the Firebase Admin SDK.
    Supports initializing from Streamlit Secrets (secrets.toml) or Environment Variables.
    """
    global db
    
    if not firebase_admin._apps:
        try:
            # Strategy 1: Check Streamlit Secrets (secrets.toml)
            has_firebase_secret = False
            try:
                has_firebase_secret = "firebase" in st.secrets
            except Exception:
                pass
                
            if has_firebase_secret:
                # Convert the secrets map to a standard dictionary
                cred_dict = dict(st.secrets["firebase"])
                
                # Format the private key to handle newline characters properly
                if "private_key" in cred_dict:
                    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
                
                # Remove storageBucket from secrets if present (ignored now)
                cred_dict.pop("storageBucket", None)
                
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                
            # Strategy 2: Check Environment Variable pointing to JSON credential filepath
            elif os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY_PATH"):
                path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY_PATH")
                cred = credentials.Certificate(path)
                firebase_admin.initialize_app(cred)
                
            # Strategy 3: Check Environment Variable containing raw JSON string
            elif os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY_JSON"):
                import json
                json_str = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY_JSON")
                cred_dict = json.loads(json_str)
                if "private_key" in cred_dict:
                    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
                
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                
            # Strategy 4: Fallback to application default credentials (ADC)
            else:
                firebase_admin.initialize_app()
                
        except Exception as e:
            # Display configuration warning in Streamlit rather than crashing the app
            st.sidebar.warning(f"⚠️ Firebase credentials not configured or initialization failed: {e}")
            return None

    # Retrieve clients if initialization succeeded
    try:
        db = firestore.client()
    except Exception as e:
        st.sidebar.warning(f"⚠️ Firestore Database client could not be initialized: {e}")
        db = None

    return db

# Trigger initialization on module import
try:
    init_firebase()
except Exception as e:
    pass
