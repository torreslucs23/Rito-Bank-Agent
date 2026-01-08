from langgraph.graph import StateGraph
import os
from langgraph.graph import StateGraph, END, START

from typing import Annotated, Optional, Literal
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from app.src.graph.nodes import *

from app.src.graph.nodes import (
    supervisor_node,
    triage_node,
)

def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("triage_agent", triage_node)


    # Set entry point - always starts with supervisor
    workflow.set_entry_point("supervisor")

    # Supervisor routes to agents or END
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "triage_agent": "triage_agent",
            "finish": END,
            END: END
        }
    )

    # All agents return to supervisor
    for agent in ["triage_agent"]:
        workflow.add_conditional_edges(
            agent,
            route_from_triage,
            {
                "supervisor": "supervisor",
                END: END
            }
        )

    print("compilando ...")
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

class AgentState(TypedDict):
    """State shared across all agents in the graph. """
    
    #conversation messages
    messages: Annotated[list, add_messages]
    
    # Auth data
    cpf_input: Optional[str]
    data_nascimento_input: Optional[str]
    autenticado: bool
    tentativas_autenticacao: int
    
    client: Optional[dict]
    
    #flow control
    next_agent: Optional[dict]
    finish: bool
    
    interview_data: Optional[dict]
    last_request: Optional[dict]