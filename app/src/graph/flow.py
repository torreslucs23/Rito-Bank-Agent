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


    # Set entry point
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
