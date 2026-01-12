import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .tools import *

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

currency_llm = ChatOpenAI(model="gpt-4o", temperature=0.5, api_key=api_key).bind_tools(
    [get_exchange_rate_tool]
)
