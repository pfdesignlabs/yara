from typing import Dict, List, TypedDict,List
import random
from langgraph.graph import StateGraph, START, END

class AgentState(TypedDict):
    """This is the state of our agent."""
    name: str
    number: int
    counter: int

def greeting_node(state: AgentState) -> AgentState:
    """This node will greet the user."""
    state['name'] = f"Hello {state['name']}!"
    state['counter'] = 0
    return state

def random_node(state: AgentState) -> AgentState:
    """This node will generate a random number."""
    state['number'] = random.randint(1, 10)
    state['counter'] += 1
    return state

def should_continue_node(state: AgentState) -> AgentState:
    """This node will decide whether to continue or not."""
    if state['counter'] < 5:
        print(f"ENTERING LOOP: {state['counter']}")
        return "loop"
    else:
        return "exit"
    
graph = StateGraph(AgentState)
graph.add_node("greeting_node", greeting_node)
graph.add_node("random_node", random_node)
graph.add_edge("greeting_node", "random_node")
graph.add_conditional_edges("random_node", should_continue_node, {"loop": "random_node", "exit": END})

graph.set_entry_point("greeting_node")

app = graph.compile()
result = app.invoke({'name': 'Jochem', 'number': [], 'counter': -1})
print(result)