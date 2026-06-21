"""
WebSocket endpoints — real-time streaming of agent steps and SQL results
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from core.auth import decode_token
from api.websocket.manager import ws_manager
from agents.pipeline import run_sqlmind
import structlog

log = structlog.get_logger()
ws_router = APIRouter()


@ws_router.websocket("/ws/query/{connection_id}")
async def websocket_query(
    websocket: WebSocket,
    connection_id: str,
    token: str = Query(...),
):
    """
    WebSocket endpoint for streaming SQL generation.

    Client sends: {"natural_language": "...", "db_type": "postgres"}
    Server streams: {"type": "agent_step", "node": "...", "data": {...}}
    Server finishes: {"type": "complete", "sql": "...", "explanation": "..."}
    Server errors: {"type": "error", "message": "..."}
    """
    # Authenticate via token query param (WebSocket can't send headers easily)
    try:
        payload = decode_token(token)
        user_id = payload["sub"]
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await ws_manager.connect(websocket, user_id)
    log.info("ws_connected", user_id=user_id, connection_id=connection_id)

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            natural_language = data.get("natural_language", "").strip()
            db_type = data.get("db_type", "postgres")

            if not natural_language:
                await websocket.send_json({"type": "error", "message": "natural_language is required"})
                continue

            # Acknowledge receipt
            await websocket.send_json({"type": "ack", "message": "Processing your query..."})

            # Streaming callback
            async def stream_to_client(event: dict):
                await websocket.send_json(event)

            # Run the agentic pipeline
            final_state = await run_sqlmind(
                natural_language=natural_language,
                connection_id=connection_id,
                user_id=user_id,
                db_type=db_type,
                stream_callback=stream_to_client,
            )

            # Send final result
            if final_state.get("guardrail_triggered"):
                await websocket.send_json({
                    "type": "guardrail_block",
                    "reason": final_state.get("guardrail_reason"),
                })
            elif final_state.get("status") == "success":
                await websocket.send_json({
                    "type": "complete",
                    "sql": final_state.get("generated_sql"),
                    "explanation": final_state.get("explanation"),
                    "agent_steps": final_state.get("agent_steps"),
                    "tokens_used": final_state.get("tokens_used"),
                    "model_used": final_state.get("model_used"),
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to generate SQL. Please rephrase your question.",
                    "errors": final_state.get("verification_errors", []),
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
        log.info("ws_disconnected", user_id=user_id)
    except Exception as e:
        log.error("ws_error", error=str(e), user_id=user_id)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        ws_manager.disconnect(user_id)
