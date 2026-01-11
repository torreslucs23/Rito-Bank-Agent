from langgraph.graph import StateGraph, END
from app.src.graph.nodes import *

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("triage_agent", triage_node)
    workflow.add_node("currency_agent", currency_agent_node)
    workflow.add_node("currency_tools", ToolNode(tools=[get_exchange_rate_tool]))

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "triage_agent": "triage_agent",
            "currency_agent": "currency_agent",
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

    return workflow.compile()

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
