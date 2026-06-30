# System Architecture & AI Evaluation Approach

This document outlines the architectural decisions, AI evaluation methodologies, and workflow logic implemented for the Visl AI Labs Candidate Screening Platform.

## 1. High-Level System Design
The application is structured as a modular, stateless frontend powered by **Streamlit**, with backend processing distributed across dedicated Python modules. 

* **Frontend (UI/UX):** Streamlit handles the interactive dashboard. To bypass Streamlit's default page-rerun behavior and support a multi-step funnel, the application heavily utilizes `st.session_state` to persist candidate datasets, OAuth tokens, and dynamic slider thresholds across user interactions.
* **Backend Processing:** Logic is separated into distinct engines (e.g., Resume Processing, GitHub API querying, LLM Evaluation).
* **Hosting & Security:** Deployed on Streamlit Community Cloud. All sensitive credentials (Gemini API keys, GitHub PAT, Google OAuth Secrets, SMTP Passwords) are strictly managed via Streamlit's `secrets.toml` vault and excluded from version control.

## 2. AI Evaluation Methodology

The core philosophy of this platform is to move beyond keyword matching by using Large Language Models (Gemini 2.5 Flash) and API data to contextually evaluate candidates against a specific Job Description (JD).

### A. Contextual Resume Parsing
Instead of standard regex-based parsers, the system uses the Gemini API to extract unstructured text from candidate PDFs. 
* **Prompt Engineering Strategy:** The LLM is instructed with a strict system prompt to act as an expert technical recruiter. It evaluates the extracted resume text against the provided JD, looking for semantic matches in core competencies, rather than exact keyword overlap.
* **Structured Output:** The LLM is forced to return structured JSON containing discrete scores for Experience, Education, and Skills, which are aggregated into a base `Resume Score`.

### B. Repository-Level GitHub Analysis
To satisfy the constraint of deep technical evaluation, the system does not rely on surface-level profile metrics (like follower count). 
* **Data Ingestion:** It utilizes the GitHub REST API to fetch a candidate's public repositories. 
* **Repository-Level Evaluation:** The system iterates through the repositories to extract the primary language, repository descriptions, and commit activity. 
* **LLM Synthesis:** This aggregated repository data is passed to the LLM to assess code quality, contribution depth, and technical relevance to the JD, generating a `GitHub Score`.

## 3. The Two-Stage Funnel (State Management)
To mimic a real-world Applicant Tracking System (ATS), the workflow is split into a two-stage funnel.

* **Stage 1: AI Screening (Top of Funnel):** The platform calculates an initial `AI Score` (a weighted combination of the Resume Score and GitHub Score). Recruiters use a real-time, dynamic UI slider to set a threshold. Candidates meeting the threshold are flagged as `SHORTLISTED_FOR_TEST`.
* **Stage 2: Final Interview (Bottom of Funnel):** Recruiters upload a secondary dataset containing Logical Aptitude and Coding test scores for the shortlisted candidates. The system calculates a `Final Composite Score`. A second dynamic slider dictates the final interview shortlist.

## 4. Automation & Integrations

### A. Human-in-the-Loop Emailing (SMTP)
The platform features an automated email drafting system. It uses a templating engine to inject candidate-specific variables (`{name}`, `{score}`) into a global email template. Crucially, it renders these drafts into an interactive `st.data_editor`, allowing the recruiter to manually review and tweak individual messages before batch-dispatching them via SMTP.

### B. Google Calendar OAuth 2.0
The application implements a secure, custom PKCE (Proof Key for Code Exchange) OAuth flow to authenticate with Google Calendar for interview scheduling.
* **State Preservation:** Because Streamlit clears query parameters on reload, the `code_verifier` and `state` variables are manually cached in `st.session_state` prior to redirecting the user to Google.
* **Token Exchange:** Upon returning, the application reconstructs the authorized URL, successfully trading the authorization code for a session-persisted credential object, enabling automated Google Meet link generation.

## 5. Resiliency & Rate Limiting
To ensure system stability when processing large batches of candidates on free-tier APIs (like Gemini):
* The AI evaluation engine implements programmatic `try-except` blocks to catch `429 RESOURCE_EXHAUSTED` errors.
* Upon hitting a rate limit, the system triggers an exponential backoff (`time.sleep()`), notifies the user via an `st.toast()`, and automatically retries the failed candidate, preventing pipeline crashes.
