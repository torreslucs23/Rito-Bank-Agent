# from langgraph.graph import StateGraph
from typing import Annotated, Literal, TypedDict, Optional
from langgraph.graph.message import add_messages
from app.src.llm.triage_llm import  triage_llm
from app.src.llm.base_llm import llm
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START
from app.src.llm.tools import save_cpf, save_birth_date
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
    
    client: Optional[dict]
    
    #flow control
    next_agent: Optional[dict]
    finish: bool
    
    interview_data: Optional[dict]
    last_request: Optional[dict]
    

system_prompt_bank = """
Você é um assistente virtual especializado em atendimento bancário. Sua função é ajudar os clientes com suas dúvidas e necessidades relacionadas aos serviços bancários. Você sempre é breve em suas mensagens, sem puxar muito assunto.
"""

triagem_prompt_bank = """
Você agora está responsável por fazer a triagem e autenticação do cliente. Responda de forma breve e profissional, seguindo as instruções abaixo.
"""
    
    


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor: analisa mensagem e decide se chama triagem ou responde direto
    """

    messages = state["messages"]
    recent_messages = messages[-30:] if len(messages) > 30 else messages
    
    system_prompt = f""" {system_prompt_bank}

Analise a mensagem do cliente:

Se o cliente disser explicitamente:
- "quero triagem"
- "fazer triagem" 
- "preciso de triagem"
- "iniciar triagem"
Ou variações similares → responda APENAS: TRIAGE

Para QUALQUER outra mensagem (saudações, perguntas, despedidas, etc) → responda APENAS: DIRECT

Mensagem do cliente: "{recent_messages[-1].content if recent_messages else ''}"

Responda APENAS UMA PALAVRA (TRIAGE ou DIRECT):"""

    response = llm.invoke([SystemMessage(content=system_prompt), *recent_messages])
    decision = response.content.strip().upper()
    
    
    if "TRIAGE" in decision:
        state['next_agent'] = 'triage_agent'
        state['waiting_for_agent'] = True
    else:
        if not state['authenticated']:
            state['next_agent'] = 'triage_agent'
            return state
        
        direct_prompt = f"""{system_prompt_bank}
Você deve simular um chatbot para essa resposta dessa última pergunta do cliente e seu histórico.
IMPORTANTE: 
- Analise TODO o histórico da conversa acima
- Seja breve, cordial e PERSONALIZADO
-> Se caso o valor esse valor aqui for: "{state['authenticated']}" for falso, peça para ele digitar o cpf para que ele possa ser autenticado. Seja breve
-> Se for verdadeiro, responda normalmente.
-> Se {state['authenticated']} == "False", basta responder algo como "Por favor, informe seu CPF para prosseguirmos com a autenticação.", sem mais nada.

Responda de forma breve e cordial. Baseie-se em coisas do contexto de mensagens que voce já tem com ele."""

        direct_response = llm.invoke([SystemMessage(content=direct_prompt), *recent_messages], temperature=0.2, max_tokens=100)
        
        state['messages'].append(AIMessage(content=direct_response.content))
        state['finish'] = True
        state['next_agent'] = None
        return state
        
def triage_node(state: AgentState) -> AgentState:
    """
    Triage Agent: Handles authentication
    """
    
    messages = state["messages"]
    last_message = messages[-1]
    recent_messages = messages[-30:] if len(messages) > 30 else messages
    
    if not state.get('cpf_input'):
        system_prompt = f"""{system_prompt_bank}
{ triagem_prompt_bank}

Seu contexto agora é coletar o CPF do cliente para autenticação.
Objetivo:
- Coletar o CPF do cliente

Instruções:
- Se o cliente forneceu um CPF (11 dígitos), chame a tool `save_cpf` com o CPF
- Se não forneceu CPF ainda, peça educadamente
- Seja breve e profissional
- Só aceite CPFs válidos (exatamente 11 dígitos). Se você identificar que o número que ele mandou tem mais de 11 digitos, responda para ele enviar o cpf novamente.
- A tool quando você chamar, você vai deixar apenas o número do cpf, sem pontos ou traços.

Exemplos de quando chamar a tool:
- Cliente: "Meu CPF é 12345678900" → CHAME save_cpf
- Cliente: "123.456.789-00" → CHAME save_cpf  
- Cliente: "Olá" → PEÇA o CPF
- Cliente: "Meu CPF é 1234" → PEÇA o CPF novamente
- Cliente: "8734897349873497349879384" → PEÇA o CPF novamente
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
                    Você tá em um fluxo de autenticação e acabou de validar o CPF do cliente.
                    O CPF informado é inválido. Por favor, informe um CPF válido com 11 dígitos. Você deve pedir isso para ele de forma educada e breve.
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
                Você tá em um fluxo de autenticação e acabou de validar o CPF do cliente.
                O CPF foi salvo. Confirme ao cliente de forma educada e pergunte a data de nascimento de forma breve para que possa seguir o processo de autenticação.
                Seja breve aqui e curto, não enrole muito
                """
            final_response = llm.invoke([
                SystemMessage(content=prompt),
                *recent_messages
            ],
                max_tokens=50,
            )
            
            state['messages'].append(AIMessage(content=final_response.content))
            print(state['messages'][-1].content)
            
        else:
            state['messages'].append(response)
            
            

    elif not state.get('birth_date'):
        system_prompt = f"""{system_prompt_bank}
        { triagem_prompt_bank}


    Contexto atual
    - CPF do cliente já foi coletado: {state['cpf_input']}

    Objetivo:
    - Coletar a DATA DE NASCIMENTO do cliente

    Instruções:
    - Se o cliente forneceu uma data de nascimento (formatos aceitos: DD/MM/AAAA, DD-MM-AAAA, DDMMAAAA), chame a tool `save_birth_date`
    - Se não forneceu ainda, peça educadamente
    - Seja breve e profissional, não enrole na resposta
    - Caso ele mandou a sua data de nascimento de alguma forma, chame a tool `save_birth_date` no formato que ela aceita.

    Exemplos de quando chamar a tool:
    - Cliente: "15/05/1990" → CHAME save_birth_date
    - Cliente: "Nasci em 15-05-1990" → CHAME save_birth_date
    - Cliente: "15051990" → CHAME save_birth_date
    - Cliente: "Oi" → PEÇA a data de nascimento
    - cliente: "128102981209981298" -> PEÇA a data de nascimento novamente
    - Cliente: "Nasci no dia 01 de agosto de 1990" -> Chame save_birth_date
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
                    Você está em um fluxo de autenticação e acabou de validar a data de nascimento do cliente.
                    A data de nascimento foi salva com sucesso. Confirme ao cliente de forma educada que a autenticação foi concluída.
                    Seja breve aqui e curto, não enrole muito
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
                    Seu está em um fluxo de autenticação e acabou de mandar uma data de nascimento inválida. Peça para ele enviar novamente de maneira educada e curta.
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
    
    
