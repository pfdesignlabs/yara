from typing import Dict, List, TypedDict,List
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    name: str
    age: int
    skills: str
    final: str

def first_node(state: AgentState) -> AgentState:
    """this is the first node in our sequence."""
    state['final'] = f"hi {state['name']}"
    return state
    
def second_node(state: AgentState) -> AgentState:
    """this is the second node in our sequence."""
    state['final'] = state['final'] + f" You are {state['age']} years old."
    return state

def third_node(state: AgentState) -> AgentState:
    """this is the third node in our sequence."""
    state['final'] = state['final'] + f" You are very skilled at {state['skills']}."
    return state

graph = StateGraph(AgentState)
graph.add_node('first_node', first_node)
graph.add_node('second_node', second_node)
graph.add_node('third_node', third_node)
graph.set_entry_point('first_node')
graph.add_edge('first_node', 'second_node',)
graph.add_edge('second_node', 'third_node',)
graph.set_finish_point('third_node')


app = graph.compile()
result = app.invoke({'name': 'Jochem', 'age': 38, 'skills': 'Python', 'skills': 'LangGraph and python'})
print(result['final'])
    
