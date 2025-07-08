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

def authentication_required(request: Request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or len(auth_header.split()) != 2:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bad authorization header')
    bearer_token = auth_header.split()[1]
    try:
        data = jwt.decode(bearer_token, config['secret_key'], algorithms=["HS256"])
    except Exception as e:
        print('Error: ', e, flush=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
    return data

def get_user(request):
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header:
            auth_token_arr = auth_header.split(" ")
            if len(auth_token_arr) == 2:
                auth_token = auth_token_arr[1]
                data = jwt.decode(auth_token, config['secret_key'], algorithms=["HS256"])
                if data:
                    email = data.get('email')
                    if email:
                        user = users_db['users'].find_one({'email': email})
                        if user:
                            user_data = {
                                '_id': str(user.get('_id')),
                                'username': user.get('username', ''),
                                'email': user.get('email', ''),
                                'password': user.get('password', ''),
                            }
                            return user_data
                        else:
                            print('User not found', flush=True)
                            return None
                    else:
                        print('Email not found in token', flush=True)
                        return None
    except Exception as e:
        print('Error: ', e, flush=True)
        return None


# @app.get('/check_auth')
# def check_auth2(user_data: dict = Depends(authentication_required)):
#     return {"message": "Hello, FastAPI!", "user": user_data}

@app.get('/check_auth')
def check_auth2(dep=Depends(authentication_required)):
    return {"message": "Hello, FastAPI!"}

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
