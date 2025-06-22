import time
import os
import re
import random
from dotenv import load_dotenv
from serpapi import GoogleSearch
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.output_parsers import StructuredOutputParser,ResponseSchema
from langchain_community.document_loaders import WebBaseLoader
from langchain.prompts import ChatPromptTemplate,HumanMessagePromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.agents import AgentExecutor,create_openai_functions_agent
from langchain import hub
import json


load_dotenv()
search_api_key = os.getenv("SERPAPI_API_KEY")
openai_key = os.environ.get("OPENAI_KEY")



@tool
def url_finder(keywords:str)->list[str]:
    """
    This function find urls given some keywords using Google search.
    """
    keyword_list = [k.strip() for k in keywords.split(",")]
    results = []
    for keyword in keyword_list:
        params = {
        "q": f"{keyword} site:analyticsvidhya.com OR site:kaggle.com OR site:medium.com",
        "api_key": search_api_key,
        "num": 2}
        search = GoogleSearch(params)
        result = search.get_dict()
        results.extend([r['link'] for r in result.get('organic_results', [])])
    return results

def clean_content(content):
    content = content.strip()
    reference_headers = ["references", "further reading", "footnotes", "sources", "citations","subscribe"]
    for header in reference_headers:
        pattern = re.compile(rf"\n{header}\s*\n", re.IGNORECASE)
        match = pattern.search(content)
        if match:
            content = content[:match.start()].strip()
            break
    content = content[400:]
    content = re.sub(r'\n\d+\.\s+.*', '', content)
    content = re.sub(r'\n+', '\n', content)
    return content.strip()

@tool
def chunk_creator(links:list[str])->list[str]:
    ''' This function takes list of urls as input and load content of that url page and return chunks of text'''
    # links = ast.literal_eval(links)
    splitter = RecursiveCharacterTextSplitter(
    chunk_size = 1000,
    chunk_overlap =  250)
    resources_chunks = []
    for link in links:
        loader = WebBaseLoader(link)
        document = loader.load()
        content = document[0].page_content
        cleaned_content = clean_content(content)
        chunks = splitter.split_text(cleaned_content)
        resources_chunks.append(chunks)
    final_chunks = [chunk for sublist in resources_chunks for chunk in sublist]
    sampled_chunks = random.sample(final_chunks,min(15,len(final_chunks)))    
    return sampled_chunks


@tool
def question_generator(chunks:list[str])-> None:
    ''' This function will create some question answer pairs, using chunks of text, given as input'''
    # chunks = ast.literal_eval(chunks)
    response_schemas = [
        ResponseSchema(
            name="qa_pairs",
            description=(
                "List of 5 multiple choice question-answer objects. "
                "Each object should have 'question', 'choices' (a list), and 'answer' fields."
            )
        )
    ]
    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

    prompt_input = prompt_input = '''Suppose you are an expert educator. Given the following topic content, generate **3 diverse and non-obvious multiple choice questions** that follow Bloom's Taxonomy (covering different cognitive levels: remember, understand, apply, analyze, evaluate, create).
                                    Each question should:
                                    - Encourage deep thinking and concept understanding
                                    - Be suitable for a technical interview
                                    - Include a list of 4 choices (A to D)
                                    - Clearly specify the correct answer

                                    Topic Content:
                                    {user_prompt}

                                    {format_instructions}'''


    prompt = ChatPromptTemplate(messages = [HumanMessagePromptTemplate.from_template(prompt_input)],
                                input_variables = ['user_prompt'],
                                partial_variables = {'format_instructions' : output_parser.get_format_instructions()})
    all_qa_pairs = {'qa_pairs':[]}
    for chunk in chunks:
        llm = ChatOpenAI(api_key=openai_key)
        chain = prompt | llm | output_parser
        qa_pairs = chain.invoke({"user_prompt" : chunk})
        all_qa_pairs['qa_pairs'].append(qa_pairs['qa_pairs'])
    with open('interview_questions.json', 'w') as json_file:
        json.dump(all_qa_pairs, json_file, indent=4)
    return 

def generate_questions(keywords):
    instructions = """You are an assistant."""
    llm = ChatOpenAI(api_key=openai_key)
    base_prompt = hub.pull("langchain-ai/openai-functions-template")
    prompt = base_prompt.partial(instructions=instructions)
    agent = create_openai_functions_agent(llm=llm,tools = [url_finder,chunk_creator,question_generator],prompt=prompt)
    agent_executor = AgentExecutor(agent=agent, tools=[url_finder,chunk_creator,question_generator], verbose=True,handle_parsing_errors=True)
    results = agent_executor.invoke({"input":f"Given some following keywords, you have to find some urls which contains contents related to them. Then you have to fetch chunks of texts from those pages and then create questions from those chunks of texts\n {keywords}"})
    return results['output']