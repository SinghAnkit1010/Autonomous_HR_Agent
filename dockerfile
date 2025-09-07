FROM python:3.11-slim

WORKDIR /HR_AGENT2


RUN pip install charset-normalizer==3.4.1
RUN pip install fastapi==0.115.12
RUN pip install google-api-core==2.24.2
RUN pip install google-api-python-client==2.170.0
RUN pip install google-auth==2.40.2
RUN pip install google-auth-httplib2==0.2.0
RUN pip install google-auth-oauthlib==1.2.2
RUN pip install google-cloud-core==2.4.3
RUN pip install google-search-results==2.4.2
RUN pip install httpcore==1.0.7
RUN pip install httplib2==0.22.0
RUN pip install httpx==0.28.1
RUN pip install httpx-sse==0.4.0
RUN pip install huggingface-hub==0.29.1
RUN pip install langchain==0.3.25
RUN pip install langchain-community==0.3.24
RUN pip install langchain-core==0.3.63
RUN pip install langchain-experimental==0.3.4
RUN pip install langchain-google-community==2.0.7
RUN pip install langchain-openai==0.3.7
RUN pip install langchain-text-splitters==0.3.8
RUN pip install langgraph-prebuilt==0.2.2
RUN pip install langgraph-sdk==0.1.70
RUN pip install numpy==2.2.3
RUN pip install oauthlib==3.2.2
RUN pip install openai==1.64.0
RUN pip install ormsgpack==1.10.0
RUN pip install packaging==24.2
RUN pip install pandas==2.2.3
RUN pip install pydantic==2.10.6
RUN pip install pydantic-settings==2.8.1
RUN pip install pypdf==5.4.0
RUN pip install python-dateutil==2.9.0.post0
RUN pip install python-dotenv==1.0.1
RUN pip install python-multipart==0.0.20
RUN pip install pytz==2025.1
RUN pip install PyYAML==6.0.2
RUN pip install regex==2024.11.6
RUN pip install requests==2.32.3
RUN pip install requests-oauthlib==2.0.0
RUN pip install rsa==4.9.1
RUN pip install scikit-learn==1.6.1
RUN pip install scipy==1.15.2
RUN pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cpu

RUN pip install starlette==0.46.2
RUN pip install transformers==4.49.0
RUN pip install uritemplate==4.1.1
RUN pip install urllib3==2.3.0
RUN pip install uvicorn==0.34.3
RUN pip install Werkzeug==3.1.3
RUN pip install beautifulsoup4==4.13.4
RUN pip install boto3==1.28.36
RUN pip install langgraph
RUN pip install sentence-transformers==3.4.1

# ENV AWS_ACCESS_KEY_ID=""
# ENV AWS_SECRET_ACCESS_KEY=""
# ENV AWS_DEFAULT_REGION=""



COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
