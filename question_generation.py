import os
import re
import json
import random
import boto3
from serpapi import GoogleSearch
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from typing import TypedDict, List, Sequence, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

search_api_key = os.getenv("SERPAPI_API_KEY")
openai_api_key = os.getenv("OPENAI_KEY")

s3 = boto3.client('s3', region_name='us-east-1')
bucket_name = 'interview-questions9408'

llm = ChatOpenAI(api_key=openai_api_key)

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

@tool
def url_finder(keywords: str) -> list[str]:
    """Find URLs given some keywords using Google search."""
    keyword_list = [k.strip() for k in keywords.split(",")]
    results = []
    for keyword in keyword_list:
        params = {
            "q": f"{keyword} site:towardsdatascience.com",
            "api_key": search_api_key,
            "num": 2
        }
        try:
            search = GoogleSearch(params)
            result = search.get_dict()
            results.extend([r['link'] for r in result.get('organic_results', [])])
        except Exception as e:
            print(f"Error searching for {keyword}: {e}")
    return results

def clean_content(content):
    content = content.strip()
    reference_headers = ["references", "further reading", "footnotes", "sources", "citations", "subscribe"]
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
def chunk_creator(links: list[str]) -> list[str]:
    ''' This function takes list of urls as input and load content of that url page and return chunks of text'''
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=250
    )
    resources_chunks = []
    for link in links:
        try:
            loader = WebBaseLoader(link)
            document = loader.load()
            content = document[0].page_content
            cleaned_content = clean_content(content)
            chunks = splitter.split_text(cleaned_content)
            resources_chunks.append(chunks)
        except Exception as e:
            print(f"Error loading {link}: {e}")
    final_chunks = [chunk for sublist in resources_chunks for chunk in sublist]
    if not final_chunks:
        return []
    sampled_chunks = random.sample(final_chunks, min(15, len(final_chunks)))
    return sampled_chunks

# def generate_questions(chunk, prompt, parser):
#     formatted_prompt = prompt.format_prompt(user_prompt=chunk)
#     response = llm.invoke(formatted_prompt.to_messages())
#     return parser.parse(response.content)

@tool
def question_generator(chunks:list[str], config: dict) -> None:
    ''' This function will create some question answer pairs, using chunks of text, given as input'''
    jd_id = config['configurable']['jd_id']
    # chunks = ast.literal_eval(chunks)
    response_schemas = [
        ResponseSchema(
            name="qa_pairs",
            description=(
                "List of 3 multiple choice question-answer objects. "
                "Each object should have 'question', 'choices' (a list), and 'answer' fields."
            )
        )
    ]
    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

    prompt_input = '''Suppose you are an expert educator. Given the following topic content, generate **3 diverse and non-obvious multiple choice questions** that follow Bloom's Taxonomy (covering different cognitive levels: remember, understand, apply, analyze, evaluate, create).
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
    llm = ChatOpenAI(api_key=openai_api_key)
    for chunk in chunks:
        chain = prompt | llm | output_parser
        qa_pairs = chain.invoke({"user_prompt" : chunk})
        all_qa_pairs['qa_pairs'].append(qa_pairs['qa_pairs'])
    s3_key = f'interview_questions_{jd_id}.json'
    s3.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(all_qa_pairs, indent=4),
        ContentType="application/json"
    )
    return all_qa_pairs



def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]

    # If LLM made no tool calls → end
    if not getattr(last_message, "tool_calls", None):
        return "end"

    # Stop if question_generator already executed once
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    if any(m.name == "question_generator" for m in tool_messages):
        return "end"

    return "continue"





def model_call(state: AgentState) -> AgentState:
    system_prompt = SystemMessage(content='You are a helpful assistant')
    response = llm.invoke([system_prompt] + state['messages'])
    return {'messages': state['messages'] + [response]}

tools = [url_finder, chunk_creator, question_generator]
llm = ChatOpenAI(api_key=openai_api_key).bind_tools(tools)

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

question_generator_agent = graph.compile()


