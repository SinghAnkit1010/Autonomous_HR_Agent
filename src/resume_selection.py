from langchain.embeddings import HuggingFaceEmbeddings
import pypdf
import requests
import json
import re
import os
from sklearn.metrics.pairwise import cosine_similarity
from langchain_core.tools import tool,Tool
import numpy as np
from langchain_google_community import GmailToolkit
from langchain_community.tools.gmail.send_message import GmailSendMessage
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from typing import Annotated
from langchain.agents import create_react_agent,AgentExecutor,create_openai_functions_agent
from langchain import hub
from pydantic import BaseModel, Field

load_dotenv()
openai_key = os.environ.get("OPENAI_KEY")
embedding_model = HuggingFaceEmbeddings(model_name="all-mpnet-base-v2")

SELECTED_CANDIDATES = []
def extract_text_from_pdf(pdf_path):
    pdf = pypdf.PdfReader(pdf_path)
    page = pdf.pages[0]
    text = page.extract_text()
    EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    email = re.findall(EMAIL_REGEX, text)[0] if re.findall(EMAIL_REGEX, text) else None
    return (text, email)

def resume_scores(resumes,job_embedding, embedding_model):
    scores = dict()
    for resume in resumes:
        resume_text,email = extract_text_from_pdf(resume)
        resume_embedding = np.array(embedding_model.embed_query(resume_text.strip())).reshape(1, -1)
        scores[email] = cosine_similarity(job_embedding, resume_embedding).flatten().tolist()[0]
    return scores


@tool
def select_top_resumes(jd:str,top_k=25):
    """Given a job description, returns the top matching resume emails from the 'resumes' folder."""
    global SELECTED_CANDIDATES
    jd_embedding = embedding_model.embed_query(jd)
    jd_embedding = np.array(jd_embedding).reshape(1, -1)
    resume_paths = os.listdir("./resumes")
    resume_paths = [os.path.join("resumes", path) for path in resume_paths]
    scores = resume_scores(resume_paths, jd_embedding, embedding_model)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_emails = [email for email, _ in sorted_scores[:top_k]]
    SELECTED_CANDIDATES = top_emails
    return top_emails


toolkit = GmailToolkit()
gmail_tools = toolkit.get_tools()

llm = ChatOpenAI(api_key=openai_key)
base_prompt = hub.pull("langchain-ai/openai-functions-template")
prompt = hub.pull("langchain-ai/openai-functions-template").partial(
    instructions="""
    You are a hiring assistant. You can:
    1. Score and select resumes from a folder given a job description.
    2. Send interview invitation emails to selected candidates using Gmail.
    """
)

def select_send_email(jd):
    agent = create_openai_functions_agent(llm=llm,tools=gmail_tools+[select_top_resumes],prompt=prompt)
    agent_executor = AgentExecutor(agent=agent, tools=gmail_tools+[select_top_resumes], verbose=True)
    input = (
        "Select top resumes for the following JD and send them an interview email.\n\n"
        f"Job Description:\n{jd}\n\n"
        "Email Subject: 'Interview Invitation'\n"
        "Message: 'Hi, you’ve been shortlisted for the next round. Please share your availability for interviews next week.'"
    )

    response = agent_executor.invoke({"input": input})
    return SELECTED_CANDIDATES