from typing import Dict, List, TypedDict,List
import random
from langgraph.graph import StateGraph, START, END

class AgentState(TypedDict):
    """This is the state of our agent."""
    player_name: str
    guesses: List[int]
    attempts: int
    lower_bound: int
    upper_bound: int