from typing import TypedDict,Annotated,List
import operator


class AgentState(TypedDict):
    messages:Annotated[List[dict],operator.add]
    current_query:str
    documents:List[str]
    plan:List[str]
    status:str
    final_answer:str
    