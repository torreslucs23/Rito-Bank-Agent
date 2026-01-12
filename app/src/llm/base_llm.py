import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI  # <--- Mudou aqui

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

llm = ChatOpenAI(model="gpt-4o", temperature=0.5, api_key=api_key)
