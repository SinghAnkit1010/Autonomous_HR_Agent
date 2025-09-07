# 🤖 Autonomous HR Agent

An AI-powered HR automation system built with FastAPI, LangGraph, and hosted on AWS.  
Automates job description creation, LinkedIn posting, resume collection & shortlisting, and interview question generation.

---

## Features
- Create Job Descriptions dynamically with AI and save in DynamoDB with unique job ID
- Post JD on LinkedIn automatically on behalf of company(With their URN)
- Store resumes in S3 and metadata in DynamoDB
- Select top candidates based on JD and resumes and send them emails
- Generate interview questions using AI
- Dockerized for easy deployment

---

## Dependencies

```txt
LangGraph
fastapi
boto3
pydantic
Docker
beautifulsoup4

## ☁️ AWS Setup

- **S3 Bucket**: `hr-agent-resume9408` → stores resumes

- **DynamoDB Tables**:
  - `LinkedinAuth` ->    stores company ID and their credentials
  - `JobDescriptions` -> stores job descriptions and metadata
  - `candidates_table` -> stores candidate information and resume links

