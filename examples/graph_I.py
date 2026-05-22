from typing import Dict, TypedDict
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    name: str

def compliment_node(state: AgentState) -> AgentState:
    """A simple node that adds a compliment to the state."""

    state['name'] = state['name'] + ", you are doing amazing job learning langgraph!"

    return state

graph = StateGraph(AgentState)
graph.add_node('compliment', compliment_node)

graph.set_entry_point('compliment')
graph.set_finish_point('compliment')

app = graph.compile()

result = app.invoke({'name': 'Jochem'})

print(result['name'])