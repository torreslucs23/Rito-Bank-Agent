import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from .tools import *



load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


triage_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.7
).bind_tools([save_cpf, save_birth_date, authenticate_customer])

