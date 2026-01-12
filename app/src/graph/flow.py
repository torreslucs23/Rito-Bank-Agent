from langgraph.graph import StateGraph, END
from app.src.graph.nodes import *
from app.src.llm.tools import *

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("triage_agent", triage_node)
    workflow.add_node("currency_agent", currency_agent_node)
    workflow.add_node("currency_tools", ToolNode(tools=[get_exchange_rate_tool]))
    
    workflow.add_node("credit_agent", credit_agent_node)
    
    workflow.add_node("credit_tools", ToolNode(tools=[process_limit_increase_request, get_score_and_or_limit]))

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "triage_agent": "triage_agent",
            "currency_agent": "currency_agent",
            "credit_agent": "credit_agent",
            "finish": END,
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "currency_agent",
        route_currency_logic, 
        {
            "currency_tools": "currency_tools",
            END: END 
        }
    )
    workflow.add_edge("currency_tools", "currency_agent")

    workflow.add_conditional_edges(
        "triage_agent",
        route_from_triage,
        {
            "supervisor": "supervisor",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "credit_agent",
        route_credit_logic,
        {
            "credit_tools": "credit_tools",
            "supervisor": "supervisor",
            "interview_agent": END,
            END: END
        }
    )
    workflow.add_edge("credit_tools", "credit_agent")

    return workflow.compile()

def route_credit_logic(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "credit_tools"

    content = last_message.content.lower()
    if "transferir" in content or "entrevista" in content:
        return "interview_agent"
        
    return END

def route_from_supervisor(state: AgentState) -> str:
    if state.get("finish"):
        return END

    next_agent = state.get("next_agent")
    if not next_agent:
        return "triage_agent"

    return next_agent



def route_from_triage(state: AgentState) -> str:
    """Triage always goes back to supervisor"""
    return END

def route_currency_logic(state: AgentState) -> str:
    """
    Decide se vai para a ToolNode ou se volta para o Supervisor/Fim.
    Substitui o 'tools_condition' padrão.
    """
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "currency_tools"
    return END 
