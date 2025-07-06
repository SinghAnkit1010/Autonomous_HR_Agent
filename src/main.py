from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
import yaml

config = yaml.load(open("/src/config.yaml"), Loader=yaml.FullLoader)

users_db_creds = config['users_db_credentials']
client_web = pymongo.MongoClient(users_db_creds['service'], users_db_creds['port'], username=users_db_creds['username'], password=users_db_creds['password'])
users_db = client_web[users_db_creds['db']]
print('list of collections in users_db:', users_db.list_collection_names(), flush=True)

data_db_credentials = config['data_db_credentials']
client_data = pymongo.MongoClient(data_db_credentials['service'], data_db_credentials['port'], username=data_db_credentials['username'], password=data_db_credentials['password'])
data_db = client_data[data_db_credentials['db']]
print('list of collections in data_db:', data_db.list_collection_names(), flush=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config['frontend_url']],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return JSONResponse(status_code=200, content={"job_description": jd})

@app.post("/post_on_linkedin")
def post_on_linkedin(jd:str):
    try:
        response = post_jd_on_linkedin(jd)
        return JSONResponse(status_code=200, content={"response": response})
    except Exception as e:
        return JSONResponse(status_code=500, content=str(e))

@app.post("/select_candidates")
def select_candidates(jd:str):
    try:
        response = select_send_email(jd)
        return JSONResponse(status_code=200, content={'response': response})
    except Exception as e:
        return JSONResponse(status_code=500, content=str(e))

@app.post("/create_questions")
def create_questions(request: KeywordRequest):
    try:
        response = generate_questions(request.keywords)
        return JSONResponse(status_code=200, content={"response": response})
    except Exception as e:
        return JSONResponse(status_code=500, content=str(e))
