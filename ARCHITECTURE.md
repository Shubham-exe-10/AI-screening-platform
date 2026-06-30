# System Architecture & AI Evaluation Approach

## System Design
The platform is built on **Streamlit** to provide a fast, reactive, and stateless frontend for recruiters. To manage the stateful nature of a multi-step recruitment pipeline, the application heavily utilizes Streamlit's `st.session_state` to persist candidate evaluations, dynamic thresholds, and OAuth PKCE verifiers across page reruns. The backend logic is modularized into dedicated Python scripts (e.g., `resume_processor.py`, `evaluation_engine.py`) to separate UI rendering from data processing.

## AI Evaluation Approach
The system evaluates candidates against a provided job description using a multi-modal approach[cite: 1]:

1. **Resume Processing:** 
   The application downloads candidate resumes and utilizes the Google Gemini API to extract unstructured text. The LLM is prompted to evaluate the extracted text against the core competencies outlined in the Job Description, returning a structured JSON score.
2. **GitHub Profile Analysis:** 
   To fulfill the constraint of repository-level evaluation[cite: 1], the system uses the GitHub REST API to fetch the candidate's public repositories. It analyzes repository descriptions, primary languages, and commit activity to measure technical depth, passing this aggregated data to the LLM for a final technical score.

## Workflow Pipeline
The application enforces a strict two-stage funnel to automate the recruitment workflow:

* **Stage 1 (AI Screening):** Candidates are scored based purely on their Resume and GitHub profiles. Recruiters use a dynamic threshold slider to shortlist candidates for testing.
* **Stage 2 (Test Administration & Scheduling):** Shortlisted candidates are sent a simulated test link. Once recruiters upload the resulting Logical Aptitude and Coding scores (CSV/Excel), a final composite score is calculated. The system then generates customized Google Meet interview invitations for the final hires