"""
File Upload Handler — supports CSV, SQLite (.db/.sqlite), SQL scripts, Excel (.xlsx)

CSV/SQLite/Excel → saved as SQLite file → queryable like any other connection
SQL script → executed on existing connection
"""
import os
import uuid
import sqlite3
import io
from pathlib import Path
from typing import Tuple
import structlog

log = structlog.get_logger()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

SUPPORTED_EXTENSIONS = {
    "csv": "CSV file — loaded as single table",
    "db": "SQLite database",
    "sqlite": "SQLite database",
    "sqlite3": "SQLite database",
    "sql": "SQL script — executed on target connection",
    "xlsx": "Excel file — each sheet becomes a table",
    "xls": "Excel file — each sheet becomes a table",
    "json": "JSON file — loaded as single table",
    "tsv": "TSV file — loaded as single table",
}


class FileUploadHandler:

    # ── CSV ───────────────────────────────────────────────────────────────────

    async def handle_csv(self, content: bytes, filename: str, delimiter: str = None) -> Tuple[str, str, dict]:
        """
        Load CSV into SQLite. Auto-detects delimiter.
        Returns: (connection_string, file_path, info)
        """
        import csv

        table_name = self._safe_table_name(filename)
        db_path = UPLOAD_DIR / f"{uuid.uuid4()}_{table_name}.db"

        # Auto-detect delimiter
        text = content.decode("utf-8-sig")  # handle BOM
        if delimiter is None:
            try:
                dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t|")
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ","

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            raise ValueError("CSV file is empty")

        headers = [self._safe_col_name(h) for h in rows[0]]
        data_rows = rows[1:]

        # Remove completely empty rows
        data_rows = [r for r in data_rows if any(cell.strip() for cell in r)]

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Try to infer column types
        col_types = self._infer_csv_types(headers, data_rows[:100])
        col_defs = ", ".join(f'"{h}" {col_types.get(h, "TEXT")}' for h in headers)
        cursor.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})')

        # Pad/truncate rows to match header count
        padded_rows = []
        for row in data_rows:
            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            elif len(row) > len(headers):
                row = row[:len(headers)]
            padded_rows.append(row)

        placeholders = ", ".join("?" * len(headers))
        cursor.executemany(f'INSERT INTO "{table_name}" VALUES ({placeholders})', padded_rows)
        conn.commit()
        conn.close()

        info = {
            "table_name": table_name,
            "rows": len(data_rows),
            "columns": headers,
            "delimiter": delimiter,
        }

        log.info("csv_uploaded", **info)
        return f"sqlite:///{db_path.absolute()}", str(db_path), info

    # ── TSV ───────────────────────────────────────────────────────────────────

    async def handle_tsv(self, content: bytes, filename: str) -> Tuple[str, str, dict]:
        return await self.handle_csv(content, filename, delimiter="\t")

    # ── SQLite ────────────────────────────────────────────────────────────────

    async def handle_sqlite(self, content: bytes, filename: str) -> Tuple[str, str, dict]:
        """Save SQLite file directly"""
        safe_name = f"{uuid.uuid4()}_{filename}"
        file_path = UPLOAD_DIR / safe_name
        file_path.write_bytes(content)

        # Verify it's a valid SQLite file
        try:
            conn = sqlite3.connect(str(file_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            conn.close()
        except Exception as e:
            file_path.unlink(missing_ok=True)
            raise ValueError(f"Invalid SQLite file: {e}")

        info = {"tables": tables, "table_count": len(tables)}
        log.info("sqlite_uploaded", path=str(file_path), tables=len(tables))
        return f"sqlite:///{file_path.absolute()}", str(file_path), info

    # ── Excel ─────────────────────────────────────────────────────────────────

    async def handle_excel(self, content: bytes, filename: str) -> Tuple[str, str, dict]:
        """Load Excel file — each sheet becomes a SQLite table"""
        try:
            import openpyxl
        except ImportError:
            try:
                import xlrd
            except ImportError:
                raise ValueError("Install openpyxl: pip install openpyxl")

        base_name = self._safe_table_name(filename)
        db_path = UPLOAD_DIR / f"{uuid.uuid4()}_{base_name}.db"
        conn = sqlite3.connect(str(db_path))

        tables_created = []
        total_rows = 0

        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                table_name = self._safe_table_name(sheet_name)

                rows = list(ws.values)
                if not rows:
                    continue

                headers = [self._safe_col_name(str(h) if h is not None else f"col_{i}") for i, h in enumerate(rows[0])]
                data_rows = []
                for row in rows[1:]:
                    data_rows.append([str(v) if v is not None else "" for v in row])

                if not headers:
                    continue

                col_defs = ", ".join(f'"{h}" TEXT' for h in headers)
                conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})')
                placeholders = ", ".join("?" * len(headers))

                # Pad rows
                padded = []
                for row in data_rows:
                    if len(row) < len(headers):
                        row = list(row) + [""] * (len(headers) - len(row))
                    padded.append(row[:len(headers)])

                conn.executemany(f'INSERT INTO "{table_name}" VALUES ({placeholders})', padded)
                tables_created.append({"table": table_name, "rows": len(data_rows), "columns": headers})
                total_rows += len(data_rows)

            wb.close()

        except Exception as e:
            conn.close()
            db_path.unlink(missing_ok=True)
            raise ValueError(f"Could not read Excel file: {e}")

        conn.commit()
        conn.close()

        info = {"sheets": tables_created, "total_rows": total_rows}
        log.info("excel_uploaded", path=str(db_path), sheets=len(tables_created))
        return f"sqlite:///{db_path.absolute()}", str(db_path), info

    # ── JSON ──────────────────────────────────────────────────────────────────

    async def handle_json(self, content: bytes, filename: str) -> Tuple[str, str, dict]:
        """Load JSON array into SQLite table"""
        import json as json_lib

        table_name = self._safe_table_name(filename)
        db_path = UPLOAD_DIR / f"{uuid.uuid4()}_{table_name}.db"

        text = content.decode("utf-8")
        data = json_lib.loads(text)

        # Handle both array and {data: [...]} formats
        if isinstance(data, dict):
            for key in ["data", "results", "rows", "items", "records"]:
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                data = [data]  # Single object

        if not isinstance(data, list) or not data:
            raise ValueError("JSON must contain an array of objects")

        # Get all unique keys as columns
        all_keys = []
        seen = set()
        for row in data[:100]:
            if isinstance(row, dict):
                for k in row.keys():
                    if k not in seen:
                        all_keys.append(k)
                        seen.add(k)

        headers = [self._safe_col_name(k) for k in all_keys]

        conn = sqlite3.connect(str(db_path))
        col_defs = ", ".join(f'"{h}" TEXT' for h in headers)
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})')

        placeholders = ", ".join("?" * len(headers))
        rows_to_insert = []
        for row in data:
            if isinstance(row, dict):
                rows_to_insert.append([str(row.get(k, "")) for k in all_keys])

        conn.executemany(f'INSERT INTO "{table_name}" VALUES ({placeholders})', rows_to_insert)
        conn.commit()
        conn.close()

        info = {"table_name": table_name, "rows": len(rows_to_insert), "columns": headers}
        log.info("json_uploaded", **info)
        return f"sqlite:///{db_path.absolute()}", str(db_path), info

    # ── SQL Script ────────────────────────────────────────────────────────────

    async def handle_sql_script(self, content: bytes, connection_string: str) -> dict:
        """
        Execute SQL script on existing connection.
        Splits by semicolons, runs each statement.
        Returns execution summary.
        """
        from sqlalchemy import create_engine, text

        sql_text = content.decode("utf-8")

        # Split into statements (handle semicolons inside strings carefully)
        statements = self._split_sql_statements(sql_text)

        engine = create_engine(connection_string, pool_pre_ping=True)
        results = []
        errors = []

        try:
            with engine.begin() as conn:
                for i, stmt in enumerate(statements):
                    stmt = stmt.strip()
                    if not stmt:
                        continue
                    try:
                        result = conn.execute(text(stmt))
                        if result.returns_rows:
                            rows = result.fetchall()
                            cols = list(result.keys())
                            results.append({
                                "statement": i + 1,
                                "sql": stmt[:100] + ("..." if len(stmt) > 100 else ""),
                                "rows": len(rows),
                                "columns": cols,
                                "preview": [[str(v) for v in row] for row in rows[:5]],
                            })
                        else:
                            results.append({
                                "statement": i + 1,
                                "sql": stmt[:100] + ("..." if len(stmt) > 100 else ""),
                                "rows_affected": result.rowcount,
                            })
                    except Exception as e:
                        errors.append({
                            "statement": i + 1,
                            "sql": stmt[:100],
                            "error": str(e),
                        })
        finally:
            engine.dispose()

        return {
            "total_statements": len(statements),
            "executed": len(results),
            "errors": errors,
            "results": results,
            "success": len(errors) == 0,
        }

    # ── Universal handler ─────────────────────────────────────────────────────

    async def handle_any(self, content: bytes, filename: str) -> Tuple[str, str, dict]:
        """Route to correct handler based on file extension"""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext == "csv":
            return await self.handle_csv(content, filename)
        elif ext == "tsv":
            return await self.handle_tsv(content, filename)
        elif ext in ("db", "sqlite", "sqlite3"):
            return await self.handle_sqlite(content, filename)
        elif ext in ("xlsx", "xls"):
            return await self.handle_excel(content, filename)
        elif ext == "sql":
            return await self.handle_sql_as_database(content, filename)
        elif ext == "json":
            return await self.handle_json(content, filename)
        else:
            raise ValueError(f"Unsupported file type: .{ext}. Supported: {', '.join(SUPPORTED_EXTENSIONS.keys())}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _safe_table_name(self, filename: str) -> str:
        name = Path(filename).stem.lower()
        name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        name = name.strip("_")
        if not name or name[0].isdigit():
            name = "data_" + name
        return name[:50]

    def _safe_col_name(self, col: str) -> str:
        col = str(col).strip().lower()
        col = "".join(c if c.isalnum() or c == "_" else "_" for c in col)
        col = col.strip("_")
        if not col or col[0].isdigit():
            col = "col_" + col
        return col[:50]

    def _infer_csv_types(self, headers: list, sample_rows: list) -> dict:
        """Infer INTEGER or REAL types from sample data"""
        types = {}
        for i, header in enumerate(headers):
            col_values = []
            for row in sample_rows:
                if i < len(row) and row[i].strip():
                    col_values.append(row[i].strip())

            if not col_values:
                types[header] = "TEXT"
                continue

            # Try integer
            try:
                [int(v) for v in col_values[:10]]
                types[header] = "INTEGER"
                continue
            except ValueError:
                pass

            # Try float
            try:
                [float(v) for v in col_values[:10]]
                types[header] = "REAL"
                continue
            except ValueError:
                pass

            types[header] = "TEXT"
        return types

    def _split_sql_statements(self, sql_text: str) -> list:
        """Split SQL script into individual statements"""
        statements = []
        current = []
        in_string = False
        string_char = None
        i = 0

        while i < len(sql_text):
            c = sql_text[i]

            # Handle string literals
            if not in_string and c in ("'", '"'):
                in_string = True
                string_char = c
                current.append(c)
            elif in_string and c == string_char:
                in_string = False
                string_char = None
                current.append(c)
            elif not in_string and c == "-" and i + 1 < len(sql_text) and sql_text[i+1] == "-":
                # Line comment — skip to end of line
                while i < len(sql_text) and sql_text[i] != "\n":
                    i += 1
                continue
            elif not in_string and c == "/" and i + 1 < len(sql_text) and sql_text[i+1] == "*":
                # Block comment — skip to */
                i += 2
                while i < len(sql_text) - 1:
                    if sql_text[i] == "*" and sql_text[i+1] == "/":
                        i += 2
                        break
                    i += 1
                continue
            elif not in_string and c == ";":
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            else:
                current.append(c)
            i += 1

        # Last statement without semicolon
        stmt = "".join(current).strip()
        if stmt:
            statements.append(stmt)

        return statements

    def delete_file(self, file_path: str):
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass

    async def handle_sql_as_database(self, content: bytes, filename: str) -> tuple:
        """
        Execute SQL file on a fresh SQLite DB — makes it queryable like CSV/Excel.
        CREATE TABLE + INSERT statements run automatically.
        Returns connection string to the new SQLite file.
        """
        base_name = self._safe_table_name(filename)
        db_path = UPLOAD_DIR / f"{uuid.uuid4()}_{base_name}.db"

        sql_text = content.decode("utf-8")
        statements = self._split_sql_statements(sql_text)

        conn = sqlite3.connect(str(db_path))
        executed = 0
        errors = []

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                conn.execute(stmt)
                executed += 1
            except Exception as e:
                errors.append({"sql": stmt[:80], "error": str(e)})

        conn.commit()

        # Get tables created
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()

        if not tables and errors:
            db_path.unlink(missing_ok=True)
            raise ValueError(f"SQL file failed: {errors[0]['error']}")

        info = {
            "tables": tables,
            "statements_executed": executed,
            "errors": errors,
        }

        log.info("sql_as_database", path=str(db_path), tables=tables, executed=executed)
        return f"sqlite:///{db_path.absolute()}", str(db_path), info