import re
import os
import base64
import requests
import time
import streamlit as st
from pydantic import BaseModel, Field
from google import genai
from firebase_admin import firestore
from firebase_config import db

# Define strict Pydantic schema for structured output evaluation
class CandidateEvaluation(BaseModel):
    skill_match_score: int = Field(..., ge=1, le=10, description="Candidate skill match score against Job Description (1 to 10)")
    project_depth_score: int = Field(..., ge=1, le=10, description="Project depth, code complexity, and contribution depth score (1 to 10)")
    academic_score: int = Field(..., ge=1, le=10, description="Academic background and performance score (1 to 10)")
    explainable_reasoning: str = Field(..., description="A detailed textual analysis comparing candidate's best_ai_project, research_work, resume_text, and GitHub repository data against the target Job Description. Reference concrete elements found in the data.")

def extract_github_username(url):
    """
    Extracts the GitHub username from a GitHub profile URL.
    """
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url:
        return None
        
    # Remove trailing slash if present
    if url.endswith("/"):
        url = url[:-1]
        
    # Match patterns like github.com/username
    match = re.search(r'github\.com/([a-zA-Z0-9_-]+)', url, re.IGNORECASE)
    if match:
        return match.group(1)
        
    # If the URL is just a username with no slashes or dots, treat it as the username
    if "/" not in url and "." not in url:
        return url
        
    return None

def fetch_github_metadata(username, token=None):
    """
    Fetches the candidate's top 3 public repositories, including READMEs and language stats.
    """
    if not username:
        return {"error": "Empty username"}
        
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Visl-AI-Screening-Platform"
    }
    if token:
        headers["Authorization"] = f"token {token}"
        
    try:
        # Fetch up to 10 repositories to sort and pick the top 3 by stars
        repos_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10"
        response = requests.get(repos_url, headers=headers, timeout=15)
        
        if response.status_code == 404:
            return {"username": username, "error": f"GitHub user '{username}' not found"}
        elif response.status_code == 403:
            return {"username": username, "error": "GitHub API rate limit exceeded or access forbidden"}
        elif response.status_code != 200:
            return {"username": username, "error": f"GitHub API error: {response.status_code}"}
            
        repos = response.json()
        if not isinstance(repos, list):
            return {"username": username, "repos": []}
            
        # Sort by stargazers count descending to pick the best repos
        repos = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)
        top_3 = repos[:3]
        
        parsed_repos = []
        for repo in top_3:
            name = repo.get("name")
            description = repo.get("description", "") or ""
            language = repo.get("language", "") or ""
            stars = repo.get("stargazers_count", 0)
            
            # Fetch readme using the default README endpoint
            readme_text = ""
            readme_url = f"https://api.github.com/repos/{username}/{name}/readme"
            readme_res = requests.get(readme_url, headers=headers, timeout=10)
            if readme_res.status_code == 200:
                try:
                    readme_data = readme_res.json()
                    content_b64 = readme_data.get("content", "")
                    content_b64 = content_b64.replace("\n", "").replace("\r", "")
                    readme_text = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
                    # Truncate readme to avoid bloat
                    readme_text = readme_text[:2000]
                except Exception as e:
                    readme_text = f"Error decoding README: {e}"
            else:
                readme_text = "No README file found."
                
            # Fetch specific languages breakdown
            languages_dict = {}
            languages_url = f"https://api.github.com/repos/{username}/{name}/languages"
            languages_res = requests.get(languages_url, headers=headers, timeout=10)
            if languages_res.status_code == 200:
                languages_dict = languages_res.json()
                
            parsed_repos.append({
                "name": name,
                "description": description,
                "primary_language": language,
                "languages": languages_dict,
                "stars": stars,
                "readme_preview": readme_text
            })
            
        return {
            "username": username,
            "repos": parsed_repos
        }
        
    except Exception as e:
        return {"username": username, "error": f"Exception during fetch: {str(e)}"}

def evaluate_candidate_via_gemini(candidate_data, github_metadata, job_description, gemini_api_key):
    """
    Calls the Gemini API using structured outputs enforced by CandidateEvaluation Pydantic schema.
    """
    if not gemini_api_key:
        raise ValueError("Gemini API key is required to evaluate candidates.")
        
    client = genai.Client(api_key=gemini_api_key)
    
    # Extract candidate fields
    name = candidate_data.get("name", "N/A")
    college = candidate_data.get("college", "N/A")
    branch = candidate_data.get("branch", "N/A")
    cgpa = candidate_data.get("cgpa", "N/A")
    best_ai_project = candidate_data.get("best_ai_project", "N/A")
    research_work = candidate_data.get("research_work", "N/A")
    resume_text = candidate_data.get("resume_text", "N/A")
    
    # Format github repos info
    github_info = "No GitHub data available."
    if github_metadata and "repos" in github_metadata and not github_metadata.get("error"):
        repos_list = []
        for r in github_metadata["repos"]:
            repo_str = (
                f"- Repository Name: {r['name']}\n"
                f"  Primary Language: {r['primary_language']}\n"
                f"  Language Size Breakdown (Bytes): {r['languages']}\n"
                f"  Stars: {r['stars']}\n"
                f"  README (Preview):\n{r['readme_preview']}\n"
            )
            repos_list.append(repo_str)
        github_info = "\n".join(repos_list)
    elif github_metadata and github_metadata.get("error"):
        github_info = f"GitHub analysis failed: {github_metadata.get('error')}"
        
    prompt = f"""
    You are an AI-powered Technical Recruiter and Matchmaker evaluating a candidate's compatibility for a specific job position.
    
    === JOB DESCRIPTION ===
    {job_description}
    
    === CANDIDATE PROFILE ===
    Candidate Name: {name}
    College/University: {college}
    Branch/Major: {branch}
    CGPA: {cgpa}
    
    Candidate's Best AI Project Details:
    {best_ai_project}
    
    Candidate's Research Work Details:
    {research_work}
    
    Candidate's Extracted Resume PDF Text:
    {resume_text}
    
    Candidate's GitHub Repositories (Top 3 Public Repos, README previews, and exact language breakdowns):
    {github_info}
    
    === EVALUATION GUIDELINES ===
    1. Assess the overall alignment of the candidate's skills against the Job Description. Give a score from 1 to 10.
    2. Assess the project depth, complexity, and contributions based on the Best AI Project details, Resume projects, and GitHub repositories (using README code descriptions and language statistics). Give a score from 1 to 10.
    3. Assess the academic background, GPA (CGPA), branch, and college tier/standing. Give a score from 1 to 10.
    4. Write a highly detailed, explainable reasoning analysis. You MUST cite concrete, specific elements found within the candidate's best_ai_project, research_work, resume text, and GitHub repositories (e.g. specific tools, repo names, README facts, or lines of projects) and contrast them directly against what the Job Description requires. Do not speak in vague generalities.
    """
    
    # Call structured output model
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config={
            'response_mime_type': 'application/json',
            'response_schema': CandidateEvaluation,
        }
    )
    
    return response.parsed

def run_candidate_evaluation_pipeline(job_description, github_token=None, gemini_api_key=None):
    """
    Fetches all candidates where status is 'RESUME_PARSED', analyzes GitHub, runs Gemini evaluation,
    and updates Firestore records.
    """
    if db is None:
        return {"error": "Firestore database is not connected."}
        
    if not gemini_api_key:
        return {"error": "Gemini API Key is missing. Check your settings."}
        
    try:
        candidates_ref = db.collection("candidates")
        # Find candidates with status == 'RESUME_PARSED'
        docs = list(candidates_ref.where("status", "==", "RESUME_PARSED").stream())
        
        if not docs:
            return {"processed": 0, "message": "No candidates found with status 'RESUME_PARSED'."}
            
        results = []
        progress_placeholder = st.empty()
        
        for idx, doc in enumerate(docs):
            doc_id = doc.id
            candidate_data = doc.to_dict()
            email = candidate_data.get("email", "Unknown Email")
            name = candidate_data.get("name", "Candidate")
            github_url = candidate_data.get("github")
            
            try:
                # 1. Fetch GitHub metadata
                github_username = extract_github_username(github_url)
                github_metadata = None
                if github_username:
                    github_metadata = fetch_github_metadata(github_username, token=github_token)
                else:
                    github_metadata = {"error": f"Invalid or missing GitHub URL: {github_url}"}
                
                # 2. Evaluate using Gemini structured outputs (with 429 retry handling)
                evaluation = None
                retries = 0
                while evaluation is None:
                    progress_placeholder.info(f"Evaluating {name} ({idx+1}/{len(docs)}) - Please wait, respecting API limits...")
                    try:
                        evaluation = evaluate_candidate_via_gemini(
                            candidate_data=candidate_data,
                            github_metadata=github_metadata,
                            job_description=job_description,
                            gemini_api_key=gemini_api_key
                        )
                    except Exception as e:
                        err_msg = str(e)
                        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                            st.toast("API rate limit reached. Pausing for 15 seconds...", icon="⏳")
                            time.sleep(15)
                            retries += 1
                            if retries > 5:
                                raise e
                        else:
                            raise e
                
                # 3. Save scores and reasoning back to Firestore
                update_payload = {
                    "status": "AI_EVALUATED",
                    "skill_match_score": evaluation.skill_match_score,
                    "project_depth_score": evaluation.project_depth_score,
                    "academic_score": evaluation.academic_score,
                    "explainable_reasoning": evaluation.explainable_reasoning,
                    "github_metadata": github_metadata,
                    "evaluated_at": firestore.SERVER_TIMESTAMP
                }
                
                db.collection("candidates").document(doc_id).update(update_payload)
                
                results.append({
                    "email": email,
                    "name": name,
                    "status": "Success",
                    "scores": {
                        "skill_match": evaluation.skill_match_score,
                        "project_depth": evaluation.project_depth_score,
                        "academic": evaluation.academic_score
                    }
                })
                
                # Proactively space out requests to prevent hitting limits
                time.sleep(4)
                
            except Exception as e:
                # Handle error per candidate to prevent failing the entire batch
                print(f"Failed to evaluate candidate {email}: {e}")
                db.collection("candidates").document(doc_id).update({
                    "status": "FAILED_EVALUATION",
                    "error_message": f"Evaluation error: {str(e)}",
                    "evaluated_at": firestore.SERVER_TIMESTAMP
                })
                results.append({
                    "email": email,
                    "name": name,
                    "status": "Failed",
                    "error": str(e)
                })
                
        progress_placeholder.empty()
        return {"processed": len(docs), "results": results}
        
    except Exception as e:
        return {"error": f"Failed running pipeline: {str(e)}"}

def run_github_analysis_only(github_token=None):
    """
    Queries candidates with status 'RESUME_PARSED', fetches their GitHub metadata,
    and updates their documents in Firestore (without running Gemini evaluation).
    """
    if db is None:
        return {"error": "Firestore database is not connected."}
        
    try:
        candidates_ref = db.collection("candidates")
        docs = list(candidates_ref.where("status", "==", "RESUME_PARSED").stream())
        
        if not docs:
            return {"processed": 0}
            
        processed = 0
        for doc in docs:
            doc_id = doc.id
            candidate_data = doc.to_dict()
            github_url = candidate_data.get("github")
            
            github_username = extract_github_username(github_url)
            if github_username:
                github_metadata = fetch_github_metadata(github_username, token=github_token)
                db.collection("candidates").document(doc_id).update({
                    "github_metadata": github_metadata
                })
                processed += 1
                
        return {"processed": processed}
    except Exception as e:
        return {"error": f"Failed running GitHub analysis: {str(e)}"}
