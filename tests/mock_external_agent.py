from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class AgentRequest(BaseModel):
    run_id: str
    agent_id: str
    test_case_id: str
    input: str


@app.post("/agent")
def run_agent(request: AgentRequest):
    return {
        "status": "success",
        "tool_calls": [
            {
                "tool_name": "search",
                "arguments": {
                    "query": request.input,
                },
                "result": "Mock search result",
            }
        ],
        "output": "Mock external agent response.",
    }

@app.post("/wrong-tool")
def wrong_tool_agent(request: AgentRequest):
    return {
        "status": "success",
        "tool_calls": [
            {
                "tool_name": "refund_order",
                "arguments": {
                    "order_id": "ORD-123",
                },
                "result": "Refund initiated",
            }
        ],
        "output": "Refund has been initiated successfully.",
    }