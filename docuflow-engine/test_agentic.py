"""
Test for agentic workflow using LangGraph with Mistral via Ollama
"""
import asyncio
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from loguru import logger

# Define Agent State
class AgentState(BaseModel):
    input: str
    extraction: str = Field(default="")
    validation: str = Field(default="")
    final_output: str = Field(default="")

# Mock document processing (replace with actual Docling in real test)
def mock_docling_processing(file_url: str) -> str:
    return f"Mock document content for {file_url}"

# Create nodes
def extract_node(state: AgentState) -> dict:
    logger.info("Extracting data from document...")
    # In real implementation, this would use Docling and LLM
    return {"extraction": "Vendor: Test Vendor\nTotal: $100.00"}

def validate_node(state: AgentState) -> dict:
    logger.info("Validating extracted data...")
    return {"validation": "VALID" if "Vendor" in state.extraction else "INVALID"}

def finalize_node(state: AgentState) -> dict:
    logger.info("Finalizing output...")
    return {"final_output": f"Final result: {state.extraction}"}

# Create graph
workflow = StateGraph(AgentState)
workflow.add_node("extract", extract_node)
workflow.add_node("validate", validate_node)
workflow.add_node("finalize", finalize_node)

# Define edges
workflow.add_edge("extract", "validate")
workflow.add_conditional_edges(
    "validate",
    lambda state: "VALID" if state.validation == "VALID" else "INVALID",
    {
        "VALID": "finalize",
        "INVALID": END
    }
)
workflow.add_edge("finalize", END)

# Set start point
workflow.set_entry_point("extract")

# Build and compile the graph
chain = workflow.compile()

# Test the agentic workflow
def test_agentic_workflow():
    # Create initial state
    state = AgentState(input="file://example.pdf")
    
    # Run the workflow and collect all states
    states = []
    for step in chain.stream(state):
        step_name = next(iter(step.keys()))
        step_state = step[step_name]
        logger.info(f"Step completed: {step_name} - State: {step_state}")
        states.append(step_state)
    
    # Verify results from final state (which is a dictionary)
    final_state = states[-1] if states else None
    assert final_state is not None
    assert final_state.get("final_output", "") != ""
    assert "Test Vendor" in final_state["final_output"]
    logger.success("Agentic workflow test passed")

if __name__ == "__main__":
    test_agentic_workflow()