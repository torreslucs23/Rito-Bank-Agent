import json
from langgraph.prebuilt import ToolNode, tools_condition
from typing import Annotated, TypedDict, Optional
from langgraph.graph.message import add_messages
from app.src.llm.credit_llm import credit_llm
from app.src.llm.triage_llm import  triage_llm
from app.src.llm.base_llm import llm
from app.src.llm.currency_llm import currency_llm
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END
from app.src.llm.tools import process_limit_increase_request, save_cpf, save_birth_date, get_exchange_rate_tool
from app.src.services.credit_service import CreditService
from app.src.services.user_service import authenticate_user

credit_service = CreditService()



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

    

system_prompt_bank = """
You are a virtual assistant specialized in banking services. Your role is to help customers with their questions and needs related to banking services. You are always brief in your messages, without making too much small talk. 
Your name is Rito. Always identify yourself as Rito when the user asks for your name or who you are.

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

system_prompt_final_instruction = """
When you send a message, try to verify if the customer is satisfied with your answer and if they need any further assistance. If they do, offer to help with anything else they
might need. If they seem satisfied, politely ask if there is anything else you can assist with before ending the conversation.
You can vary your closing phrases to keep the conversation engaging and friendly.
avoid to use always "Posso ajudar com mais alguma coisa?" in the end of your responses.
You can use some emojis to make the conversation more friendly, but don't overuse them. Use sometimes.
Always answer in portuguese (Brazilian Portuguese).
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
    
    # ... (início da função supervisor_node) ...

    # 1. ATUALIZAÇÃO NO PROMPT
    system_prompt = f""" {system_prompt_bank}

Analyze the customer's message:

If the customer explicitly says they want to know the value of a currency, conversion or something similar:
- "qual a cotação do dólar?"
- "me informe o valor do euro"
- "qual o valor do bitcoin hoje?"
- "quero saber a cotação da libra"
Or similar variations → respond ONLY: CURRENCY

if the customer explicitly talks about "limit", "credit increase", "score", "credit card":
- "quero aumentar meu limite"
- "qual meu limite atual?"
- "liberar mais crédito"
or other similar variations → respond ONLY: CREDIT

If the customer wants to EXIT, quit, say goodbye or end the conversation:
- "sair"
- "tchau"
- "encerrar atendimento"
- "obrigado, tchau"
- "fechar"
- "valeu, flw"
Or similar variations → respond ONLY: EXIT

For ANY other message (greetings, questions, farewells, etc) → respond ONLY: DIRECT

Customer's message: "{recent_messages[-1].content if recent_messages else ''}"

{system_prompt_final_instruction}

Respond with ONLY ONE WORD (CURRENCY, CREDIT, EXIT or DIRECT):"""

    response = llm.invoke([SystemMessage(content=system_prompt), *recent_messages])
    decision = response.content.strip().upper()
    
    # 2. LÓGICA DE ROTEAMENTO E LIMPEZA
    
    if "CURRENCY" in decision:
        state['next_agent'] = 'currency_agent'
        return state
    
    elif "CREDIT" in decision:
        state['next_agent'] = 'credit_agent'
        return state

    elif "EXIT" in decision:        
        goodbye_message = AIMessage(content="O Rito Bank agradece seu contato! Sessão encerrada com segurança. Até a próxima!")
        state['messages'] = [goodbye_message]
        
        state['authenticated'] = False
        state['cpf_input'] = None
        state['birth_date'] = None
        state['next_agent'] = END
        
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
        
        
        Remember the services you have as an bank agent. You just have these services, if the user asks for them:
        - consult the credit limit and score
        - consult the currency exchange rates
        - you can increase the customer's credit limit

        {system_prompt_final_instruction}
        """

        direct_response = llm.invoke([SystemMessage(content=direct_prompt), *recent_messages], temperature=0.5, max_tokens=100)
        
        state['messages'].append(AIMessage(content=direct_response.content))
        state['next_agent'] = END
        return state
        
def triage_node(state: AgentState) -> AgentState:
    """
    Triage Agent: Handles authentication
    """
    
    messages = state["messages"]
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


{system_prompt_final_instruction}

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
                    
                    {system_prompt_final_instruction}
                    
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
                
                {system_prompt_final_instruction}
                
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

{system_prompt_final_instruction}

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
                    
                    {system_prompt_final_instruction}
                    
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
                    
                    {system_prompt_final_instruction}
                    
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
    
    {system_prompt_final_instruction}
    
    REMEMBER: Respond in Portuguese.
    """

    response = currency_llm.invoke([SystemMessage(content=system_prompt), *messages], temperature=0.4, max_tokens=150)
    return {"messages": [response]}


def credit_agent_node(state: AgentState) -> AgentState:
    messages = state["messages"]
    
    
    client_context = f"""
    LOGGED CLIENT DATA:
    Name: {state.get('name', 'N/A')}
    CPF: {state.get('cpf_input', 'N/A')}
    Current Score: {state.get('score', 0)}
    Current Limit: R$ {state.get('credit_limit', 0)}
    """

    last_message = messages[-1]

    if isinstance(last_message, ToolMessage) and last_message.tool_call_id == "process_limit_increase_request":
        
        tool_output = last_message.content.lower()
        is_rejected = "rejeitado" in tool_output
        
        if is_rejected:
            system_prompt = f"""
            {system_prompt_bank}
            You are a Credit Agent.
            
            The customer's limit increase request was REJECTED by the system.
            
            YOUR MISSION NOW:
            1. Inform the rejection in an empathetic and professional manner.
            2. MANDATORY: Offer to conduct a "Credit Profile Interview" YOURSELF right now.
               - Explain that you can collect updated financial data (income, expenses) to recalculate their score immediately.
               - Use a phrasing like: "If you wish, I can start a profile analysis interview now to try to adjust your score."
            3. If the customer agrees (says YES), respond exactly: "Vou iniciar a entrevista agora."
            
            {system_prompt_final_instruction}
            
            Respond in Portuguese.
            """
        else:
            system_prompt = f"""
            {system_prompt_bank}
            You are a Credit Agent.
            The request was APPROVED.
            
            YOUR MISSION:
            1. Congratulate the customer.
            2. Confirm the new limit.
            3. Ask if you can help with anything else.
            
            {system_prompt_final_instruction}
            
            Respond in Portuguese.
            """
            
        response = llm.invoke(
            [SystemMessage(content=system_prompt), *messages[-10:]],
            temperature=0.3
        )
        return {"messages": [response]}

    else:
                
        system_prompt = f"""
        {system_prompt_bank}
        
        CLIENT CONTEXT:
        {client_context}
        
        YOUR RESPONSIBILITIES:
        1. If the customer asks about the current limit, use the tool "get_score_and_or_limit" to retrieve the most up-to-date information.
        
        2. If the customer requests a LIMIT INCREASE:
           - Check if they mentioned the desired value.
           - If they DID NOT mention the value, ask: "Para qual valor você deseja aumentar seu limite?"
           - If they ALREADY mentioned the value, CALL THE TOOL `process_limit_increase_request` immediately.
           - Use the data (CPF, Current Limit, Score) that is already in the context to fill the tool arguments.
        
        3. If the customer accepts to go to the interview (after a previous rejection):
           - Just say you will transfer them.
           
        Be direct and professional. If he asks something about the information, some tip, prepare a good response.
        
        {system_prompt_final_instruction}
        
        Respond in Portuguese.
        """
        
        response = credit_llm.invoke(
            [SystemMessage(content=system_prompt), *messages[-10:]],
            temperature=0.3,
            max_tokens=300
        )
        
        return {"messages": [response]}