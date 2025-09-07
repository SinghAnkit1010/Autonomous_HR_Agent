from langchain_openai import ChatOpenAI
import openai
import os
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate


load_dotenv()
openai_key = os.environ.get("OPENAI_KEY")
def jd_create(data):
    print(openai_key)
    llm = ChatOpenAI(api_key = openai_key)
    parser = StrOutputParser()
    template = PromptTemplate(template = '''You are a recruiter. You have to create a job description for the following role:{role},
                            for location {location}.
                            The candidate should have the following skills:{skills}.
                            The candidate should have the {experience} years of expirence in {skills} skills.
                            The candidate should have the following education:{education}.''',
                            input_variables=["role","skills","experience","education"],)
    chain = template | llm | parser
    output = chain.invoke(input = data.dict())
    return output
    
