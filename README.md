# Visl AI Labs: Candidate Screening Platform

An AI-powered recruitment automation platform designed to evaluate candidates through intelligent resume parsing, repository-level GitHub analysis, and dynamic test scoring. Built for the Visl AI Labs Founding AI Engineer assignment.

## Core Features
* **Automated Data Ingestion:** Process candidate batches via CSV/Excel uploads.
* **AI Resume Parsing:** Extracts skills, education, and experience using Gemini LLMs.
* **GitHub Repository Analysis:** Evaluates candidate technical contributions at the repository level.
* **Dynamic Pipeline:** A two-stage shortlisting funnel separating AI evaluation from final test score grading.
* **Automated Communication:** Generates dynamic email drafts and simulates Google Meet interview scheduling.

## Local Setup Instructions

1. **Clone the Repository**
   git clone <your-github-repo-url>
   cd <your-repo-name>

2. **Install Dependencies**
   pip install -r requirements.txt

3. **Configure Secrets**
   Create a hidden folder and file at `.streamlit/secrets.toml` in the root directory. Add your credentials:
   
   GEMINI_API_KEY = "your_api_key"
   GITHUB_TOKEN = "your_github_token"
   SMTP_EMAIL = "your_email@gmail.com"
   SMTP_PASSWORD = "your_app_password"
   OAUTH_CLIENT_ID = "your_oauth_id"
   OAUTH_CLIENT_SECRET = "your_oauth_secret"

4. **Run the Application**
   streamlit run app.py