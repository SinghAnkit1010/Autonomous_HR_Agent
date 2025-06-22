from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from create_jd import jd_create
from linkedin_post import post_jd_on_linkedin
from resume_selection import select_send_email
from question_generation import generate_questions
from linkedin_auth import router as linkedin_router
from fastapi.responses import JSONResponse
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# load_dotenv()

app = FastAPI()
app.include_router(linkedin_router)

class KeywordRequest(BaseModel):
    keywords: str

class jd_data(BaseModel):
    role : str
    location : str
    skills : str
    experience : int
    education : str
    link : str


@app.get("/")
def func():
    return {"message":"welcome to Autonomous HR Agent"}


@app.post("/create_jd")
def create_job_description(data:jd_data):
    jd = jd_create(data)
    return JSONResponse(status_code=200,content={"job_description":jd})

@app.post("/post_on_linkedin")
def post_on_linkedin(jd:str):
    try:
        response = post_jd_on_linkedin(jd)
        return JSONResponse(status_code = 200,content = {"response":response})
    except Exception as e:
        return JSONResponse(status_code=500,content=str(e))


@app.post("/select_candidates")
def select_candidates(jd:str):
    try:
        response = select_send_email(jd)
        return JSONResponse(status_code=200,content={'response':response})
    except Exception as e:
        return JSONResponse(status_code=500,content=str(e))


@app.post("/create_questions")
def create_questions(request: KeywordRequest):
    try:
        response = generate_questions(request.keywords)
        return JSONResponse(status_code=200, content={"response": response})
    except Exception as e:
        return JSONResponse(status_code=500, content=str(e))