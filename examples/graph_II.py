from typing import Dict, TypedDict, List
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    values: List[int]
    name: str
    operation: str
    result: str

def process_values(state: AgentState) -> AgentState:
    """A simple node that processes the values in the state."""

    if state['operation'] == '+':
        calculation = sum(state['values'])
    elif state['operation'] == '*':
        calculation = 1
        for value in state['values']:
            calculation *= value
    
    state['result'] = f"hi {state['name']}, the total of your values is {calculation}."

    return state

graph = StateGraph(AgentState)
graph.add_node('process_values', process_values)
graph.set_entry_point('process_values')
graph.set_finish_point('process_values')    
app = graph.compile()
result = app.invoke({'name': 'Jochem', 'values': [1, 2, 7], 'operation': '+'})
print(result['result'])