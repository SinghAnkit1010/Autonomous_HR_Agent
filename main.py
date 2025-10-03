from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi import UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from create_jd import jd_create
from linkedin_post import post_jd_on_linkedin
from question_generation import question_generator_agent
from resume_selection import resume_selection_agent
from linkedin_auth import router as linkedin_router
from fastapi.responses import JSONResponse
import uuid
import boto3
from datetime import datetime
import bs4
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import os


load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL_DEVELOPMENT"), os.getenv("FRONTEND_URL_PRODUCTION")],  # Frontend origin
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

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
jd_table = dynamodb.Table('JobDescriptions')
candidates_table = dynamodb.Table("candidates_table")


s3 = boto3.client('s3', region_name='us-east-1')

@app.get("/")
def func():
    return {"message":"welcome to Autonomous HR Agent"}


@app.post("/create_jd")
def create_job_description(data:jd_data):
    jd = jd_create(data)
    jd_id = str(uuid.uuid4())

    apply_page_link = f"http://54.236.15.84:8000//apply/{jd_id}"
    jd += f"\n\nTo apply, please visit: {apply_page_link}"

    item = {
        "jd_id": jd_id,
        "job_description": jd,
        "role": data.role,
        "location": data.location,
        "skills": data.skills,
        "experience": data.experience,
        "education": data.education,
        "link": apply_page_link
    }

    jd_table.put_item(Item=item)
    return JSONResponse(status_code=200,content={"jd_id":jd_id,"job_description":jd})

@app.post("/post_on_linkedin")
def post_on_linkedin(jd_id:str,company_id:str):
    try:
        response = post_jd_on_linkedin(jd_id,company_id)
        return JSONResponse(status_code = 200,content = {"response":response})
    except Exception as e:
        return JSONResponse(status_code=500,content=str(e))

@app.get("/apply/{jd_id}", response_class=HTMLResponse)
def apply_page(jd_id: str):
    # This serves an HTML form (simple)
    return f"""
    <html>
        <body>
            <h2>Apply for Job ID: {jd_id}</h2>
            <form action="/upload_resume" enctype="multipart/form-data" method="post">
                <input type="hidden" name="jd_id" value="{jd_id}" />
                <label>Name:</label><br>
                <input type="text" name="candidate_name" required/><br>
                <label>Email:</label><br>
                <input type="email" name="email" required/><br>
                <label>Upload Resume:</label><br>
                <input type="file" name="file" accept=".pdf,.doc,.docx" required/><br><br>
                <input type="submit" value="Submit"/>
            </form>
        </body>
    </html>
    """


@app.post("/upload_resume")
async def upload_resume(
    file: UploadFile = File(...),
    candidate_name: str = Form(...),
    email: str = Form(...),
    jd_id: str = Form(...)):
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_key = f"resumes/{jd_id}/{candidate_name}_{timestamp}_{file.filename}"

        # Upload to S3
        bucket_name = 'hr-agent-resume9408'
        s3.upload_fileobj(file.file, bucket_name, file_key)

        # Create S3 URL
        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{file_key}"

        # Store metadata in DynamoDB
        resume_id = str(uuid.uuid4())

        candidates_table.put_item(
            Item={
                "resume_id": resume_id,
                "jd_id": jd_id,
                "candidate_name": candidate_name,
                "email": email,
                "file_key": file_key,
                "s3_url": s3_url,
                "uploaded_at": timestamp
            }
        )

        return {
            "message": "Resume uploaded successfully",
            "resume_id": resume_id,
            "s3_url": s3_url
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/select_candidates")
def select_candidates(jd_id:str):
    try:
        jd_response = jd_table.get_item(Key={"jd_id": jd_id})
        jd = jd_response["Item"]["job_description"]
        input_text = f"Given the following job description, select top matching resumes from the resumes stored in S3 bucket and send emails to the candidates:\n\n{jd}"
        response = resume_selection_agent.invoke({'messages':[HumanMessage(content=input_text)]})
        return JSONResponse(status_code=200,content={'response':response['messages'][-1].content})
    except Exception as e:
        return JSONResponse(status_code=500,content=str(e))


@app.post("/create_questions")
def create_questions(request: KeywordRequest, jd_id: str):
    try:
        config = {"configurable": {"jd_id": jd_id}}
        input_text = f"Given some following keywords, you have to find some urls which contains contents related to them. Then you have to fetch chunks of texts from those pages and then create questions from those chunks of texts\n {request.keywords} and save them in S3 bucket, with the following configuration: {config}"
        response = question_generator_agent.invoke({'messages':[HumanMessage(content=input_text)]}, config=config)

        return JSONResponse(status_code=200, content={"response": response['messages'][-1].content})
    except Exception as e:
        return JSONResponse(status_code=500, content=str(e))
    

# @app.get("/get_questions/{jd_id}")
# def get_questions(jd_id: str):
#     try:
#         s3_key = f"interview_questions/{jd_id}.json"
#         bucket_name = 'interview_questions9408'
#         response = s3.get_object(Bucket=bucket_name, Key=s3_key)
#         questions_data = response['Body'].read().decode('utf-8')
#         return JSONResponse(status_code=200, content={"questions": questions_data})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": str(e)})
    



