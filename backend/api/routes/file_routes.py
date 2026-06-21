"""
File Routes — unified file upload and SQL execution endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import structlog

from db.session import get_db
from core.auth import get_current_user
from models.models import User, DatabaseConnection
from agents.schema_agent import SchemaAgent
from api.routes.upload import FileUploadHandler, SUPPORTED_EXTENSIONS

log = structlog.get_logger()
router = APIRouter()
upload_handler = FileUploadHandler()


@router.get("/supported-types")
async def get_supported_types():
    """List all supported file types"""
    return {
        "database_files": {
            "csv": "CSV file — auto-detects delimiter, type inference",
            "tsv": "Tab-separated values",
            "db": "SQLite database file",
            "sqlite": "SQLite database file",
            "sqlite3": "SQLite database file",
            "xlsx": "Excel — each sheet becomes a table",
            "xls": "Excel (legacy format)",
            "json": "JSON array of objects",
        },
        "script_files": {
            "sql": "SQL script — executed on existing connection",
        },
        "max_size_mb": 50,
    }


@router.post("/database")
async def upload_database_file(
    file: UploadFile = File(...),
    name: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload CSV, SQLite, Excel, JSON, TSV file as a queryable database connection.
    Creates a new connection that can be used in the query editor.
    """
    content = await file.read()
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Validate extension
    database_types = {"csv", "tsv", "db", "sqlite", "sqlite3", "xlsx", "xls", "json", "sql"}
    if ext not in database_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type .{ext} not supported for database upload. "
                   f"Supported: {', '.join(sorted(database_types))}"
        )

    # Size check
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 50MB.")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    try:
        connection_string, file_path, info = await upload_handler.handle_any(content, filename)

        # Save as connection
        encrypted = SchemaAgent.encrypt(connection_string)
        conn = DatabaseConnection(
            user_id=current_user.id,
            name=name or filename,
            db_type="sqlite",
            connection_string_encrypted=encrypted,
            is_active=True,
        )
        db.add(conn)
        await db.commit()
        await db.refresh(conn)

        # Invalidate schema cache
        try:
            from db.redis_client import get_redis
            redis = get_redis()
            if redis:
                await redis.delete(f"schema_full:{conn.id}")
        except Exception:
            pass

        return {
            "id": str(conn.id),
            "name": conn.name,
            "db_type": "sqlite",
            "file_type": ext,
            "file_info": info,
            "message": f"Successfully uploaded {filename} as a queryable database",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("file_upload_failed", error=str(e), filename=filename)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/sql-script")
async def execute_sql_script(
    file: UploadFile = File(...),
    connection_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute a .sql script file on an existing database connection.
    Runs each statement and returns results summary.
    """
    content = await file.read()
    filename = file.filename or "script.sql"
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext != "sql":
        raise HTTPException(status_code=400, detail="Only .sql files accepted for script execution")

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="SQL file too large. Maximum 5MB.")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="SQL file is empty.")

    # Get connection
    result = await db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.is_active == True,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    agent = SchemaAgent(app_db_session=db)
    connection_string = agent._decrypt(connection.connection_string_encrypted)

    try:
        result = await upload_handler.handle_sql_script(content, connection_string)

        # Invalidate schema cache (SQL script may have created new tables)
        try:
            from db.redis_client import get_redis
            redis = get_redis()
            if redis:
                await redis.delete(f"schema_full:{connection_id}")
        except Exception:
            pass

        return {
            "filename": filename,
            "connection_name": connection.name,
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/preview")
async def preview_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview a file before uploading — shows first 10 rows and column names.
    Does NOT create a connection.
    """
    content = await file.read()
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower()

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Preview file too large. Maximum 10MB.")

    try:
        if ext == "csv":
            import csv, io
            text = content.decode("utf-8-sig")
            try:
                dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t|")
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ","
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = list(reader)
            if not rows:
                raise ValueError("Empty file")
            headers = rows[0]
            preview_rows = rows[1:11]
            return {
                "filename": filename,
                "file_type": "csv",
                "columns": headers,
                "preview_rows": preview_rows,
                "total_rows_estimate": len(rows) - 1,
                "delimiter": repr(delimiter),
            }

        elif ext in ("db", "sqlite", "sqlite3"):
            import sqlite3, io as _io
            conn = sqlite3.connect(":memory:")
            conn.deserialize(content)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            table_info = []
            for tname in tables[:5]:
                cursor.execute(f'SELECT * FROM "{tname}" LIMIT 5')
                rows = cursor.fetchall()
                cols = [d[0] for d in cursor.description]
                table_info.append({"table": tname, "columns": cols, "preview": rows})
            conn.close()
            return {
                "filename": filename,
                "file_type": "sqlite",
                "tables": tables,
                "table_previews": table_info,
            }

        elif ext in ("xlsx", "xls"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheets = []
            for sheet_name in wb.sheetnames[:3]:
                ws = wb[sheet_name]
                rows = list(ws.values)[:6]
                if rows:
                    sheets.append({
                        "sheet": sheet_name,
                        "columns": [str(v) for v in rows[0]],
                        "preview": [[str(v) if v is not None else "" for v in row] for row in rows[1:]],
                    })
            wb.close()
            return {"filename": filename, "file_type": "excel", "sheets": sheets}

        elif ext == "json":
            import json as json_lib
            data = json_lib.loads(content.decode("utf-8"))
            if isinstance(data, dict):
                for key in ["data", "results", "rows", "items"]:
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
            if isinstance(data, list) and data:
                keys = list(data[0].keys()) if isinstance(data[0], dict) else []
                preview = [[str(row.get(k, "")) for k in keys] for row in data[:5]]
                return {"filename": filename, "file_type": "json", "columns": keys,
                        "preview_rows": preview, "total_rows": len(data)}

        else:
            raise HTTPException(status_code=400, detail=f"Preview not supported for .{ext}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not preview file: {str(e)}")
