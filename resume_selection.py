from langchain.embeddings import HuggingFaceEmbeddings
import pypdf
import boto3
import requests
import io
import re
import os
from sklearn.metrics.pairwise import cosine_similarity
from typing import TypedDict, List, Sequence, Annotated
from langgraph.graph.message import add_messages
from langchain_core.tools import tool,Tool
import numpy as np
from langchain_google_community import GmailToolkit
from langchain_community.tools.gmail.send_message import GmailSendMessage
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage, SystemMessage

load_dotenv()
openai_key = os.environ.get("OPENAI_KEY")
embedding_model = HuggingFaceEmbeddings(model_name="all-mpnet-base-v2")

s3 = boto3.client("s3")
bucket_name = 'hr-agent-resume9408'

llm = ChatOpenAI(api_key=openai_key)

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


EMAIL_RE = re.compile(
    r'(?:(?<=^)|(?<=[^\w.+-]))'      # left boundary: start or a non-email char
    r'(?:pe|✉|✉️|📧|||)?\s*'      # optional envelope/icon junk sometimes decoded as 'pe'
    r'([A-Za-z0-9][A-Za-z0-9._%+-]*' # local part (capture STARTS here)
    r'@[A-Za-z0-9.-]+\.[A-Za-z]{2,})' # domain
)

ZERO_WIDTH = re.compile(r'[\u200b-\u200f\u202a-\u202e]')

def extract_emails_clean(text: str):
    # normalize typical PDF artifacts
    text = ZERO_WIDTH.sub('', text)                    # strip zero-width chars
    text = re.sub(r'\s+@\s+', '@', text)               # fix split '@'
    text = re.sub(r'\s+\.\s+', '.', text)              # fix split '.'
    # find clean emails; returns only the captured group (no 'pe')
    emails = EMAIL_RE.findall(text)
    # dedupe, preserve order
    seen = set(); out = []
    for e in emails:
        if e not in seen:
            seen.add(e); out.append(e)
    return out


SELECTED_CANDIDATES = []
def extract_text_from_pdf(pdf):
    pdf = pypdf.PdfReader(pdf)
    page = pdf.pages[0]
    text = page.extract_text()
    emails = extract_emails_clean(text)
    email = emails[0] if emails else None
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
    """Given a job description, returns the top matching resume emails from the resume stored in S3 bucket"""
    global SELECTED_CANDIDATES
    resume_paths = []
    jd_embedding = embedding_model.embed_query(jd)
    jd_embedding = np.array(jd_embedding).reshape(1, -1)
    response = s3.list_objects_v2(Bucket=bucket_name)
    if 'Contents' not in response:
        return []
    for obj in response.get("Contents", []):
        key = obj["Key"]
        print("Reading:", key)

        file_obj = s3.get_object(Bucket=bucket_name, Key=key)
        pdf_content = file_obj["Body"].read()

        resume_paths.append(io.BytesIO(pdf_content))

    # resume_paths = [item['Key'] for item in response['Contents'] if item['Key'].endswith('.pdf')]
    scores = resume_scores(resume_paths, jd_embedding, embedding_model)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_emails = [email for email, _ in sorted_scores[:top_k]]
    SELECTED_CANDIDATES = top_emails
    return top_emails


toolkit = GmailToolkit()
gmail_tools = toolkit.get_tools()

def should_continue(state: AgentState):
    messages = state['messages']
    last_message = messages[-1]
    if not getattr(last_message, "tool_calls", None):
        return 'end'
    else:
        return 'continue'


def model_call(state: AgentState) -> AgentState:
    system_prompt = SystemMessage(content='You are a hiring assistant who can help in selecting candidates and sending emails. Use the tool to select top resumes and send emails to them.')
    response = llm.invoke([system_prompt] + state['messages'])
    return {'messages': state['messages'] + [response]}

tools = [select_top_resumes] + gmail_tools
llm = ChatOpenAI(api_key=openai_key).bind_tools(tools)

graph = StateGraph(AgentState)
graph.add_node('our_agent', model_call)
tool_node = ToolNode(tools=tools)
graph.add_node('tool_node', tool_node)
graph.add_edge(START, 'our_agent')
graph.add_conditional_edges(
    source='our_agent',
    path=should_continue,
    path_map={'continue': 'tool_node', 'end': END}
)
graph.add_edge('tool_node', 'our_agent')

resume_selection_agent = graph.compile()


