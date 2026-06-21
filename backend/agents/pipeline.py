"""
SQLMind Pipeline — optimized for latency
Changes:
1. Guardrail + Schema run in parallel (saves 2-3 sec)
2. Gemini Flash model
3. Max iterations 2 (was 3)
4. Q&A answer generation built in
"""
import time
import asyncio
from typing import TypedDict, Literal, Optional, List
from langgraph.graph import StateGraph, END
import structlog

from core.config import settings
from guardrails.guardrail_engine import GuardrailEngine
from agents.sql_generator import SQLGeneratorAgent
from agents.verifier import VerifierAgent
from agents.explainer import ExplainerAgent

log = structlog.get_logger()


class SQLMindState(TypedDict):
    natural_language: str
    connection_id: str
    user_id: str
    db_type: str
    connection_string: Optional[str]
    schema_context: str
    relevant_tables: List[str]
    schema_rag_chunks: List[dict]
    generated_sql: str
    sql_iterations: int
    max_iterations: int
    verification_passed: bool
    verification_errors: List[str]
    safety_check_passed: bool
    explanation: str
    guardrail_triggered: bool
    guardrail_reason: str
    agent_steps: List[dict]
    tokens_used: int
    model_used: str
    error: Optional[str]
    status: str
    _db_session: Optional[object]


def get_llm(temperature: float = 0.1):
    if settings.DEFAULT_LLM == "openai" and settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.LLM_MODEL, temperature=temperature,
                          api_key=settings.OPENAI_API_KEY, max_tokens=settings.MAX_TOKENS)
    elif settings.GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=temperature,
            google_api_key=settings.GOOGLE_API_KEY,
        )
    else:
        raise ValueError("No LLM API key configured. Set OPENAI_API_KEY or GOOGLE_API_KEY in .env")


async def orchestrator_node(state: SQLMindState) -> dict:
    log.info("orchestrator_node", nl=state["natural_language"][:80])

    # Run guardrail + schema fetch in PARALLEL — key latency optimization
    guardrail = GuardrailEngine()

    from agents.schema_agent import SchemaAgent
    db_session = state.get("_db_session")
    schema_agent = SchemaAgent(app_db_session=db_session)

    guardrail_task = asyncio.create_task(guardrail.check_input(state["natural_language"]))
    schema_task = asyncio.create_task(schema_agent.get_relevant_schema(
        connection_id=state["connection_id"],
        natural_language=state["natural_language"],
        db_type=state["db_type"],
        connection_string=state.get("connection_string"),
    ))

    guardrail_result, schema_result = await asyncio.gather(guardrail_task, schema_task)

    if guardrail_result.blocked:
        return {
            "guardrail_triggered": True,
            "guardrail_reason": guardrail_result.reason,
            "status": "blocked",
            "schema_context": "",
            "relevant_tables": [],
            "schema_rag_chunks": [],
            "agent_steps": [{
                "node": "orchestrator",
                "action": "guardrail_block",
                "reason": guardrail_result.reason,
                "timestamp": time.time(),
            }]
        }

    return {
        "guardrail_triggered": False,
        "status": "running",
        "sql_iterations": 0,
        "max_iterations": 2,
        "verification_passed": False,
        "safety_check_passed": False,
        "schema_context": schema_result.schema_text,
        "relevant_tables": schema_result.relevant_tables,
        "schema_rag_chunks": schema_result.rag_chunks,
        "agent_steps": [{
            "node": "orchestrator",
            "action": "input_validated",
            "guardrail_score": guardrail_result.score,
            "table_count": schema_result.table_count,
            "rag_chunks_used": len(schema_result.rag_chunks),
            "timestamp": time.time(),
        }]
    }


async def sql_generator_node(state: SQLMindState) -> dict:
    log.info("sql_generator_node", iteration=state.get("sql_iterations", 0))
    llm = get_llm(temperature=0.05)
    agent = SQLGeneratorAgent(llm=llm)
    result = await agent.generate(
        natural_language=state["natural_language"],
        schema_context=state["schema_context"],
        db_type=state["db_type"],
        previous_errors=state.get("verification_errors", []),
        rag_chunks=state.get("schema_rag_chunks", []),
    )
    steps = state.get("agent_steps", [])
    steps.append({"node": "sql_generator", "action": "sql_generated",
                  "iteration": state.get("sql_iterations", 0) + 1,
                  "tokens_used": result.tokens_used, "timestamp": time.time()})
    return {"generated_sql": result.sql, "sql_iterations": state.get("sql_iterations", 0) + 1,
            "tokens_used": state.get("tokens_used", 0) + result.tokens_used,
            "model_used": "gemini-1.5-flash", "agent_steps": steps}


async def verifier_node(state: SQLMindState) -> dict:
    log.info("verifier_node")
    agent = VerifierAgent()
    result = await agent.verify(sql=state["generated_sql"], schema_context=state["schema_context"],
                                relevant_tables=state["relevant_tables"], db_type=state["db_type"])
    steps = state.get("agent_steps", [])
    steps.append({"node": "verifier", "action": "verification_complete", "passed": result.passed,
                  "safety_passed": result.safety_passed, "errors": result.errors,
                  "hallucination_score": result.hallucination_score, "timestamp": time.time()})
    return {"verification_passed": result.passed, "safety_check_passed": result.safety_passed,
            "verification_errors": result.errors, "agent_steps": steps}


async def explainer_node(state: SQLMindState) -> dict:
    log.info("explainer_node")
    try:
        llm = get_llm(temperature=0.3)
        agent = ExplainerAgent(llm=llm)
        explanation = await agent.explain(sql=state["generated_sql"],
                                          natural_language=state["natural_language"],
                                          schema_context=state["schema_context"])
    except Exception as e:
        explanation = f"Query generates SQL to answer: {state['natural_language']}"
    steps = state.get("agent_steps", [])
    steps.append({"node": "explainer", "action": "explanation_generated", "timestamp": time.time()})
    return {"explanation": explanation, "status": "success", "agent_steps": steps}


def route_after_orchestrator(state: SQLMindState) -> Literal["sql_generator", "done"]:
    return "done" if state.get("guardrail_triggered") else "sql_generator"


def route_after_verifier(state: SQLMindState) -> Literal["sql_generator", "explainer", "done"]:
    if state.get("verification_passed") and state.get("safety_check_passed"):
        return "explainer"
    if state.get("sql_iterations", 0) >= state.get("max_iterations", 2):
        return "done"
    return "sql_generator"


def build_sqlmind_graph():
    graph = StateGraph(SQLMindState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("explainer", explainer_node)
    graph.set_entry_point("orchestrator")
    graph.add_conditional_edges("orchestrator", route_after_orchestrator,
                                {"sql_generator": "sql_generator", "done": END})
    graph.add_edge("sql_generator", "verifier")
    graph.add_conditional_edges("verifier", route_after_verifier,
                                {"sql_generator": "sql_generator", "explainer": "explainer", "done": END})
    graph.add_edge("explainer", END)
    return graph.compile()


sqlmind_graph = build_sqlmind_graph()


async def run_sqlmind(natural_language: str, connection_id: str, user_id: str,
                      db_type: str = "postgres", connection_string: str = None,
                      db_session=None, stream_callback=None) -> SQLMindState:
    initial_state: SQLMindState = {
        "natural_language": natural_language, "connection_id": connection_id,
        "user_id": user_id, "db_type": db_type, "connection_string": connection_string,
        "schema_context": "", "relevant_tables": [], "schema_rag_chunks": [],
        "generated_sql": "", "sql_iterations": 0, "max_iterations": 2,
        "verification_passed": False, "verification_errors": [], "safety_check_passed": False,
        "explanation": "", "guardrail_triggered": False, "guardrail_reason": "",
        "agent_steps": [], "tokens_used": 0, "model_used": "gemini-1.5-flash",
        "error": None, "status": "pending", "_db_session": db_session,
    }
    if stream_callback:
        async for event in sqlmind_graph.astream(initial_state):
            node_name = list(event.keys())[0]
            node_output = event[node_name]
            await stream_callback({"type": "agent_step", "node": node_name,
                                   "data": {k: v for k, v in node_output.items()
                                            if k not in ("agent_steps", "_db_session")}})
    final_state = await sqlmind_graph.ainvoke(initial_state)
    return final_state
