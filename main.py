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
import pymongo
import traceback
import jwt
import datetime
from functools import wraps
from fastapi import Request, HTTPException, status, Depends
import uuid

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
    link: str

def authentication_required(request: Request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or len(auth_header.split()) != 2:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bad authorization header')
    bearer_token = auth_header.split()[1]
    print('Bearer token:', bearer_token, flush=True)
    try:
        data = jwt.decode(bearer_token, config['secret_key'], algorithms=["HS256"])
    except Exception as e:
        print('Error: ', e, flush=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
    return data

def get_user(token_data):
    email = token_data.get('email')
    if not email:
        return None
    user = users_db['users'].find_one({'email': email})
    if user:
        return {
            '_id': str(user.get('_id')),
            'username': user.get('username', ''),
            'email': user.get('email', ''),
            'password': user.get('password', ''),
        }
    return None

@app.get('/check_auth')
def check_auth2(dep=Depends(authentication_required)):
    return {"message": "Hello, FastAPI!"}

@app.get("/")
def func():
    return {"message":"welcome to Autonomous HR Agent"}

@app.post("/create_jd")
def create_job_description(data: jd_data, dep=Depends(authentication_required)):
    jd_id = uuid.uuid4().hex
    data.link = f"{config['frontend_url']}/job/{jd_id}/apply"
    jd = jd_create(data)
    user_data = get_user(dep)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    payload = {
        "_id": jd_id,
        "jd": jd,
        "role": data.role,
        "location": data.location,
        "skills": data.skills,
        "experience": data.experience,
        "education": data.education,
        "link": data.link,
        "user_id": user_data['_id'],
        "created_at": datetime.datetime.utcnow()
    }
    data_db['job_descriptions'].insert_one(payload)
    return JSONResponse(status_code=200, content={"message": 'Job description created successfully', "job_id": jd_id})

@app.post("/post_on_linkedin")
def post_on_linkedin(jd:str, dep=Depends(authentication_required)):
    try:
        response = post_jd_on_linkedin(jd)
        return JSONResponse(status_code=200, content={"response": response})
    except Exception as e:
        return JSONResponse(status_code=500, content=str(e))

@app.post("/select_candidates")
def select_candidates(jd:str, dep=Depends(authentication_required)):
    try:
        response = select_send_email(jd)
        return JSONResponse(status_code=200, content={'response': response})
    except Exception as e:
        return JSONResponse(status_code=500, content=str(e))

@app.post("/create_questions")
def create_questions(request: KeywordRequest, dep=Depends(authentication_required)):
    try:
        response = generate_questions(request.keywords)
        return JSONResponse(status_code=200, content={"response": response})
    except Exception as e:
        return JSONResponse(status_code=500, content=str(e))
