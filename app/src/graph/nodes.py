import json
from langgraph.prebuilt import ToolNode, tools_condition
from typing import Annotated, TypedDict, Optional
from langgraph.graph.message import add_messages
from app.src.llm.triage_llm import  triage_llm
from app.src.llm.base_llm import llm
from app.src.llm.currency_llm import currency_llm
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END
from app.src.llm.tools import save_cpf, save_birth_date, get_exchange_rate_tool
from app.src.services.user_service import authenticate_user




class AgentState(TypedDict):
    """State shared across all agents in the graph. """
    #conversation messages
    messages: Annotated[list, add_messages]
    
    # Auth data
    cpf_input: Optional[str]
    birth_date: Optional[str]
    authenticated: bool
    authentication_attempts: int
    
    
    #flow control
    next_agent: Optional[dict]
    finish: bool

    

system_prompt_bank = """
You are a virtual assistant specialized in banking services. Your role is to help customers with their questions and needs related to banking services. You are always brief in your messages, without making too much small talk. 
Your name is Rito. Always identify yourself as Rito and say you are the bank agent assistant, in the first message of the conversation.

IMPORTANT: Always provide your responses in Portuguese (Brazilian Portuguese).
"""

triagem_prompt_bank = """
You are now responsible for triaging and authenticating the customer. Respond briefly and professionally, following the instructions below.

IMPORTANT: Always provide your responses in Portuguese (Brazilian Portuguese).
"""

exchange_prompt_bank = """
You are now responsible for providing information about currency exchange. Respond briefly and professionally, following the instructions below.

IMPORTANT: Always provide your responses in Portuguese (Brazilian Portuguese).
"""
    
    


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor: analyzes message and decides whether to call triage or respond directly
    """

    messages = state["messages"]
    recent_messages = messages[-20:] if len(messages) > 20 else messages
    
    if not state['authenticated']:
        state['next_agent'] = 'triage_agent'
        return state
    
    system_prompt = f""" {system_prompt_bank}

Analyze the customer's message:



If the customer explicitly says they want to know the value of a currency, conversion or something similar:
- "qual a cotação do dólar?"
- "me informe o valor do euro"
- "qual o valor do bitcoin hoje?"
- "quero saber a cotação da libra"
Or similar variations → respond ONLY: CURRENCY

For ANY other message (greetings, questions, farewells, etc) → respond ONLY: DIRECT

Customer's message: "{recent_messages[-1].content if recent_messages else ''}"

Respond with ONLY ONE WORD (CURRENCY or DIRECT):"""

    response = llm.invoke([SystemMessage(content=system_prompt), *recent_messages])
    decision = response.content.strip().upper()
    

    
    if "CURRENCY" in decision:
        state['next_agent'] = 'currency_agent'
        return state
    
    else:
        state_for_prompt = state.copy()
        state_for_prompt.pop("messages", None)
    
        state_context_str = json.dumps(state_for_prompt, indent=2, ensure_ascii=False)
        direct_prompt = f"""{system_prompt_bank}
        
        ROLE: You are a friendly banking assistant handling general conversation (Direct Interaction).

        OBJECTIVE: Respond politely and professionally to greetings, thanks, or random comments from the customer.
        
        this is some information about the client that might help you:
        {state_context_str}

        INSTRUCTIONS:
        1. **Personalize:** If you see the client's name in 'Client Information', use it naturally (e.g., "Olá, Lucas!", "Como posso ajudar, Maria?").
        2. **Be Natural:** Respond to the user's greeting, thanks, or random comment politely.
        3. **No Auth Block:** Do NOT ask for CPF/Authentication automatically. Only ask if the user requests a restricted service (like checking balance).
        4. **Style:** Be brief, professional, and warm.

        LANGUAGE: Respond STRICTLY in Portuguese (PT-BR).
        """

        direct_response = llm.invoke([SystemMessage(content=direct_prompt), *recent_messages], temperature=0.2, max_tokens=100)
        
        state['messages'].append(AIMessage(content=direct_response.content))
        state['next_agent'] = END
        return state
        
def triage_node(state: AgentState) -> AgentState:
    """
    Triage Agent: Handles authentication
    """
    
    messages = state["messages"]
    last_message = messages[-1]
    recent_messages = messages[-20:] if len(messages) > 20 else messages
    
    if not state.get('cpf_input'):
        system_prompt = f"""{system_prompt_bank}
{triagem_prompt_bank}

Your current context is to collect the customer's CPF for authentication.
Objective:
- Collect the customer's CPF

Instructions:
- If the customer provided a CPF (11 digits), call the `save_cpf` tool with the CPF
- If they haven't provided the CPF yet, ask politely and mention it's for authentication
- Be brief and professional
- Only accept valid CPFs (exactly 11 digits). If you identify that the number they sent has more than 11 digits, respond asking them to send the CPF again.
- When calling the tool, you will leave only the CPF number, without dots or dashes.

Examples of when to call the tool:
- Customer: "Meu CPF é 12345678900" → CALL save_cpf
- Customer: "123.456.789-00" → CALL save_cpf  
- Customer: "Olá" → ASK for the CPF
- Customer: "Meu CPF é 1234" → ASK for the CPF again
- Customer: "8734897349873497349879384" → ASK for the CPF again

REMEMBER: Respond in Portuguese.
"""
        
        response = triage_llm.invoke([
            SystemMessage(content=system_prompt),
            *recent_messages
        ],
        max_tokens=100,
        temperature=0.3 )
        
        if response.tool_calls:
            tool_call = response.tool_calls[0]
            cpf_result = save_cpf.invoke(tool_call["args"])
            
            if not cpf_result['success']:
                state['messages'].append(response)
                state['messages'].append(ToolMessage(
                    content=str(cpf_result),
                    tool_call_id=tool_call["id"]
                ))            
                prompt = f"""
                    {system_prompt_bank}
                    {triagem_prompt_bank}
                    You are in an authentication flow and just validated the customer's CPF.
                    The provided CPF is invalid. Please inform a valid CPF with 11 digits. You should ask them for this in a polite and brief manner.
                    
                    REMEMBER: Respond in Portuguese.
                    """
                response_llm = llm.invoke(
                    [
                        SystemMessage(content=prompt),
                        *recent_messages
                    ],
                    max_tokens=50,
                )
                state['messages'].append(AIMessage(content=response_llm.content))
                state['next_agent'] = END
                return state
                        
            state['cpf_input'] = cpf_result['cpf']
            
            state['messages'].append(response)
            state['messages'].append(ToolMessage(
                content=str(cpf_result),
                tool_call_id=tool_call["id"]
            ))
            prompt = f"""
                {system_prompt_bank}
                {triagem_prompt_bank}
                You are in an authentication flow and just validated the customer's CPF.
                The CPF was saved. Confirm to the customer politely and ask for the date of birth briefly so the authentication process can continue.
                Be brief and short here, don't drag it out.
                
                REMEMBER: Respond in Portuguese.
                """
            final_response = llm.invoke([
                SystemMessage(content=prompt),
                *recent_messages
            ],
                max_tokens=50,
            )
            
            state['messages'].append(AIMessage(content=final_response.content))
            
        else:
            state['messages'].append(response)
            
            

    elif not state.get('birth_date'):
        system_prompt = f"""{system_prompt_bank}
{triagem_prompt_bank}


Current context:
- Customer's CPF has already been collected: {state['cpf_input']}

Objective:
- Collect the customer's DATE OF BIRTH

Instructions:
- If the customer provided a date of birth (accepted formats: DD/MM/YYYY, DD-MM-YYYY, DDMMYYYY), call the `save_birth_date` tool
- If they haven't provided it yet, ask politely
- Be brief and professional, don't drag out the response
- If they sent their date of birth in some way, call the `save_birth_date` tool in the format it accepts.

Examples of when to call the tool:
- Customer: "15/05/1990" → CALL save_birth_date
- Customer: "Nasci em 15-05-1990" → CALL save_birth_date
- Customer: "15051990" → CALL save_birth_date
- Customer: "Oi" → ASK for date of birth
- Customer: "128102981209981298" -> ASK for date of birth again
- Customer: "Nasci no dia 01 de agosto de 1990" -> CALL save_birth_date

REMEMBER: Respond in Portuguese.
"""
        
        response = triage_llm.invoke(
        [
            SystemMessage(content=system_prompt),
            *recent_messages
        ],
        max_tokens=100,
        temperature=0.3
        )
        
        if response.tool_calls:
            tool_call = response.tool_calls[0]
            birth_date_result = save_birth_date.invoke(tool_call["args"])
            
            if birth_date_result['success']:
                
                user_is_authenticated = authenticate_user(state['cpf_input'], birth_date_result['birth_date'])
                if(not user_is_authenticated['authenticated']):
                    state['authentication_attempts'] += 1
                    if(state['authentication_attempts'] >=3):
                        state['messages'].append(AIMessage(
                            content="Número máximo de tentativas de autenticação atingido. Vamos encerrar o atendimento por aqui."
                        ))
                        state['next_agent'] = END
                        state['birth_date'] = None
                        state['cpf_input'] = None
                        return state
                    else:
                        state['messages'].append(AIMessage(
                            content="Autenticação falhou. Por favor, verifique seus dados e envie o cpf novamente para reiniciar o processo de autenticação."
                        ))
                        state['birth_date'] = None
                        state['cpf_input'] = None
                        return state
                    
                state['birth_date'] = birth_date_result['birth_date']
                
                state['messages'].append(response)
                state['messages'].append(ToolMessage(
                    content=str(birth_date_result),
                    tool_call_id=tool_call["id"]
                ))
                prompt = f"""
                    {system_prompt_bank}
                    {triagem_prompt_bank}
                    You are in an authentication flow and just validated the customer's date of birth.
                    The date of birth was saved successfully. Confirm to the customer politely that authentication has been completed.
                    Be brief and short here, don't drag it out.
                    
                    REMEMBER: Respond in Portuguese.
                    """
                final_response = llm.invoke(
                    [
                        SystemMessage(content=prompt),
                        *recent_messages
                    ],
                max_tokens=100,
                temperature=0.3)
                
                state['messages'].append(AIMessage(content=final_response.content))
                state['authenticated'] = True
                return state
            else:
                state['messages'].append(response)
                response  = llm.invoke(
                    f"""
                    {system_prompt_bank}
                    {triagem_prompt_bank}
                    You are in an authentication flow and just sent an invalid date of birth. Ask them to send it again in a polite and brief manner.
                    
                    REMEMBER: Respond in Portuguese.
                    """
                ,
                max_tokens=50,
                temperature=0.2)
                state['messages'].append(AIMessage(
                    content=response.content
                ))
        else:
            state['messages'].append(response)
        
    
    state['next_agent'] = END
    return state
    
  
def currency_agent_node(state: AgentState) -> AgentState:
    """
    Currency Exchange Agent with Reasoning (ReAct).
    """
    messages = state["messages"][-10:] if len(state["messages"]) > 10 else state["messages"]
    
    system_prompt = f"""
    {system_prompt_bank}
    You are an expert trader and currency exchange assistant.
    Your `get_exchange_rate_tool` tool provides quotes relative to the REAL (BRL).

    MANDATORY EXECUTION STRATEGY:
    
    GOLDEN RULE (ANTI-LOOP):
    1. Before calling any tool, LOOK AT THE HISTORY above.
    2. If you ALREADY SEE a 'ToolMessage' message with the currency value you want, DO NOT CALL THE TOOL AGAIN.
    3. Just take that value, do the calculation and respond to the user.
    
    CASE 1: The user wants a currency quote to Real (e.g., Dollar).
    -> Call the tool for the requested currency.

    CASE 2: The user wants conversion between two foreign currencies (e.g., Pound to Dollar).
    -> Step A: Call the tool for the first currency (e.g., GBP).
    -> Step B: Call the tool for the second currency (e.g., USD).
    -> Step C: WAIT for the tools to return. The system will give you the values back.
    -> Step D: With the values in hand, do the mathematical division (Value1 / Value2) and respond to the customer.

    CRITICAL RULES:
    1. DO NOT explain the calculation before having the numbers. GET THE NUMBERS FIRST.
    2. If you don't have the value of a mentioned currency, CALL THE TOOL. Don't apologize, act.
    3. You can call multiple tools at the same time if needed.
    
    At the end, respond directly: "A conversão de X para Y é Z. Posso ajudar em mais alguma coisa?" Don't respond with anything beyond something similar to this, if you have the result.
    
    REMEMBER: Respond in Portuguese.
    """

    response = currency_llm.invoke([SystemMessage(content=system_prompt), *messages], temperature=0.1)
    return {"messages": [response]}

