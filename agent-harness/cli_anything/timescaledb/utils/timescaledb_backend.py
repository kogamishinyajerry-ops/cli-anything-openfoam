"""
timescaledb_backend.py - TimescaleDB CLI wrapper

Wraps TimescaleDB operations via psql and timescaledb_toolkit commands.

TimescaleDB is installed via:
  - Linux: install from timescale.com or apt install timescaledb-2-postgresql
  - macOS: brew install timescale-postgresql
  - Docker: docker pull timescale/timescaledb:latest-pg16

Principles:
  - Database operations via SQL executed through psql
  - TimescaleDB-specific features: hypertables, continuous aggregates, compression
  - Mock mode for testing without database connection
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# -------------------------------------------------------------------
# Version
# -------------------------------------------------------------------

TIMESCALEDB_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Installation detection
# -------------------------------------------------------------------

def find_psql() -> Path:
    """Find psql binary."""
    psql_path = os.environ.get("PSQL_PATH")
    if psql_path:
        return Path(psql_path)

    try:
        result = subprocess.run(
            ["which", "psql"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass

    # Common paths
    paths = ["/usr/bin/psql", "/usr/local/bin/psql"]
    for p in paths:
        if Path(p).exists():
            return Path(p)

    raise RuntimeError(
        "psql not found. Set PSQL_PATH or install PostgreSQL client."
    )


def get_connection_params(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> dict:
    """Get connection parameters from env or defaults."""
    return {
        "host": host or os.environ.get("PGHOST", "localhost"),
        "port": port or int(os.environ.get("PGPORT", "5432")),
        "user": user or os.environ.get("PGUSER", "postgres"),
        "password": password or os.environ.get("PGPASSWORD", ""),
        "dbname": dbname or os.environ.get("PGDATABASE", "postgres"),
    }


def build_psql_cmd(sql: str, params: dict, extra_args: Optional[list] = None) -> list:
    """Build psql command with connection parameters."""
    cmd = [str(find_psql())]
    if params.get("host"):
        cmd.extend(["-h", params["host"]])
    if params.get("port"):
        cmd.extend(["-p", str(params["port"])])
    if params.get("user"):
        cmd.extend(["-U", params["user"]])
    if params.get("dbname"):
        cmd.extend(["-d", params["dbname"]])
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(["-c", sql])
    return cmd


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a TimescaleDB command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run_sql(
    sql: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    timeout: int = 30,
    check: bool = True,
) -> CommandResult:
    """Execute SQL via psql."""
    params = get_connection_params(host, port, user, password, dbname)
    cmd = build_psql_cmd(sql, params)

    env = os.environ.copy()
    if params.get("password"):
        env["PGPASSWORD"] = params["password"]

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=env,
        )
        duration = time.time() - start

        if check and proc.returncode != 0:
            return CommandResult(
                success=False,
                output=proc.stdout,
                error=proc.stderr,
                returncode=proc.returncode,
                duration_seconds=duration,
            )

        return CommandResult(
            success=proc.returncode == 0,
            output=proc.stdout,
            error=proc.stderr,
            returncode=proc.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            output="",
            error="Query timed out after {}s".format(timeout),
            returncode=-1,
            duration_seconds=timeout,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            output="",
            error=str(e),
            returncode=-99,
            duration_seconds=time.time() - start,
        )


# -------------------------------------------------------------------
# Version / Info
# -------------------------------------------------------------------

def get_version() -> dict:
    """Get TimescaleDB version."""
    if os.environ.get("TIMESCALEDB_MOCK"):
        return {
            "success": True,
            "version": "2.14.2",
            "timescaledb_version": "2.14.2",
            "postgres_version": "16.4",
        }

    sql = "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"
    result = _run_sql(sql, timeout=15, check=False)

    if result.success and result.output.strip():
        version = result.output.strip()
        # Also get PostgreSQL version
        pg_result = _run_sql("SHOW server_version;", timeout=5, check=False)
        pg_version = pg_result.output.strip() if pg_result.success else "unknown"
        return {
            "success": True,
            "version": version,
            "timescaledb_version": version,
            "postgres_version": pg_version,
        }

    return {
        "success": False,
        "error": result.error or "TimescaleDB extension not found",
    }


# -------------------------------------------------------------------
# Database operations
# -------------------------------------------------------------------

def list_hypertables(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> dict:
    """List all hypertables in the database."""
    if os.environ.get("TIMESCALEDB_MOCK"):
        return {
            "success": True,
            "hypertables": [
                {"Name": "conditions", "schema": "public", "dimensions": 1, "chunks": 3},
                {"Name": "cpu_usage", "schema": "public", "dimensions": 1, "chunks": 5},
            ],
        }

    sql = (
        "SELECT hypertable_name, hypertable_schema, num_dimensions, num_chunks "
        "FROM timescaledb_information.hypertables "
        "ORDER BY hypertable_name;"
    )
    result = _run_sql(sql, host, port, user, password, dbname, timeout=15, check=False)

    if not result.success:
        return {"success": False, "error": result.error}

    hypertables = []
    for line in result.output.strip().split("\n"):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4 and parts[0] != "hypertable_name":
            try:
                hypertables.append({
                    "Name": parts[0],
                    "schema": parts[1],
                    "dimensions": int(parts[2]),
                    "chunks": int(parts[3]),
                })
            except (ValueError, IndexError):
                pass

    return {"success": True, "hypertables": hypertables}


def create_hypertable(
    table_name: str,
    time_column: str,
    space_columns: Optional[str] = None,
    chunk_interval: Optional[str] = None,
    if_not_exists: bool = True,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> CommandResult:
    """
    Create a TimescaleDB hypertable.

    Args:
        table_name: Name of the table (or schema.table)
        time_column: Name of the time column
        space_columns: Optional comma-separated space partitioning columns
        chunk_interval: Optional chunk interval (e.g. '1 day', '1 hour')
        if_not_exists: Add IF NOT EXISTS clause
        host/port/user/password/dbname: Connection parameters

    Returns:
        CommandResult
    """
    if os.environ.get("TIMESCALEDB_MOCK"):
        return CommandResult(
            success=True,
            output="Created hypertable: {}".format(table_name),
            returncode=0,
        )

    ie = "IF NOT EXISTS" if if_not_exists else ""
    sql_parts = [
        "SELECT create_hypertable(",
        "'{}'::regclass,".format(table_name),
        "time_column => '{}'::text".format(time_column),
    ]

    if space_columns:
        sql_parts.append(", partition_column => '{}'".format(space_columns))

    if chunk_interval:
        sql_parts.append(", chunk_interval => interval '{}'".format(chunk_interval))

    sql_parts.append(");")
    sql = "".join(sql_parts).replace("'(", "('").replace(")'", "')")

    return _run_sql(sql, host, port, user, password, dbname, timeout=30, check=False)


def hypertable_info(
    table_name: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> dict:
    """Get detailed info about a hypertable."""
    if os.environ.get("TIMESCALEDB_MOCK"):
        return {
            "success": True,
            "Name": table_name,
            "schema": "public",
            "dimensions": 1,
            "chunks": 3,
            "compression_enabled": False,
            "retention_enabled": False,
        }

    sql = (
        "SELECT * FROM timescaledb_information.hypertables "
        "WHERE hypertable_name = '{}'".format(table_name)
    )
    result = _run_sql(sql, host, port, user, password, dbname, timeout=15, check=False)

    if not result.success:
        return {"success": False, "error": result.error}

    return {
        "success": True,
        "raw_output": result.output,
        "table_name": table_name,
    }


# -------------------------------------------------------------------
# Continuous aggregates
# -------------------------------------------------------------------

def create_continuous_aggregate(
    aggregate_name: str,
    view_name: str,
    bucket_column: str,
    bucket_interval: str,
    group_columns: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> CommandResult:
    """
    Create a continuous aggregate.

    Args:
        aggregate_name: Name for the continuous aggregate view
        view_name: Source hypertable or view
        bucket_column: Time bucket column
        bucket_interval: Bucket interval (e.g. '1 hour', '1 day')
        group_columns: Additional group by columns

    Returns:
        CommandResult
    """
    if os.environ.get("TIMESCALEDB_MOCK"):
        return CommandResult(
            success=True,
            output="Created continuous aggregate: {}".format(aggregate_name),
            returncode=0,
        )

    group_clause = ""
    if group_columns:
        group_clause = ", {}".format(group_columns)

    sql = (
        "CREATE MATERIALIZED VIEW {} "
        "WITH (timescaledb.continuous) AS "
        "SELECT time_bucket('{}', {}){} "
        "FROM {} "
        "GROUP BY time_bucket('{}', {}){};"
    ).format(
        aggregate_name,
        bucket_interval, bucket_column,
        group_clause,
        view_name,
        bucket_interval, bucket_column,
        group_clause,
    )

    return _run_sql(sql, host, port, user, password, dbname, timeout=60, check=False)


def list_continuous_aggregates(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> dict:
    """List all continuous aggregates."""
    if os.environ.get("TIMESCALEDB_MOCK"):
        return {
            "success": True,
            "aggregates": [
                {"Name": "device_summary", "view_name": "metrics", "bucket": "1 hour"},
            ],
        }

    sql = (
        "SELECT view_name, materials hypertable_name, bucket_column, bucket_interval "
        "FROM timescaledb_information.continuous_aggregates;"
    )
    result = _run_sql(sql, host, port, user, password, dbname, timeout=15, check=False)

    if not result.success:
        return {"success": False, "error": result.error}

    aggregates = []
    for line in result.output.strip().split("\n"):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4 and parts[0] != "view_name":
            aggregates.append({
                "Name": parts[0],
                "view_name": parts[1],
                "bucket": parts[3],
            })

    return {"success": True, "aggregates": aggregates}


# -------------------------------------------------------------------
# Compression
# -------------------------------------------------------------------

def enable_compression(
    table_name: str,
    segment_by: Optional[str] = None,
    order_by: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> CommandResult:
    """Enable compression on a hypertable."""
    if os.environ.get("TIMESCALEDB_MOCK"):
        return CommandResult(
            success=True,
            output="Compression enabled on: {}".format(table_name),
            returncode=0,
        )

    chunk_parts = ["ALTER TABLE {}", "SET (timescaledb.compress, timescaledb.compress_segmentby = '{}'"]
    sql = "ALTER TABLE {} SET (timescaledb.compress, timescaledb.compress_segmentby = '{}');".format(
        table_name, segment_by or "device_id"
    )

    return _run_sql(sql, host, port, user, password, dbname, timeout=30, check=False)


def compression_info(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> dict:
    """Get compression statistics."""
    if os.environ.get("TIMESCALEDB_MOCK"):
        return {
            "success": True,
            "compressed_chunks": 5,
            "total_chunks": 10,
            "compressed_bytes": 1024000,
            "uncompressed_bytes": 5120000,
            "compression_ratio": 5.0,
        }

    sql = (
        "SELECT hypertable_name, num_chunks_compressed, num_chunks_total, "
        "round(total_compressed_bytes::numeric / 1024, 2) as compressed_kb, "
        "round(total_uncompressed_bytes::numeric / 1024, 2) as uncompressed_kb "
        "FROM timescaledb_information.compression_stats "
        "ORDER BY hypertable_name;"
    )
    result = _run_sql(sql, host, port, user, password, dbname, timeout=15, check=False)

    if not result.success:
        return {"success": False, "error": result.error}

    return {
        "success": True,
        "raw_output": result.output,
    }


# -------------------------------------------------------------------
# Data operations
# -------------------------------------------------------------------

def insert_from_csv(
    table_name: str,
    csv_path: str,
    delimiter: str = ",",
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> CommandResult:
    """
    Insert data from CSV into a table.

    Args:
        table_name: Target table name
        csv_path: Path to CSV file
        delimiter: CSV delimiter

    Returns:
        CommandResult
    """
    csv = Path(csv_path)
    if not csv.exists():
        return CommandResult(
            success=False,
            error="CSV file not found: {}".format(csv),
            returncode=1,
        )

    if os.environ.get("TIMESCALEDB_MOCK"):
        row_count = sum(1 for _ in csv.read_text().split("\n") if _.strip()) - 1
        return CommandResult(
            success=True,
            output="Inserted {} rows into {}".format(max(0, row_count), table_name),
            returncode=0,
        )

    params = get_connection_params(host, port, user, password, dbname)
    psql = find_psql()
    env = os.environ.copy()
    if params.get("password"):
        env["PGPASSWORD"] = params["password"]

    cmd = [str(psql)]
    if params.get("host"):
        cmd.extend(["-h", params["host"]])
    if params.get("port"):
        cmd.extend(["-p", str(params["port"])])
    if params.get("user"):
        cmd.extend(["-U", params["user"]])
    if params.get("dbname"):
        cmd.extend(["-d", params["dbname"]])
    cmd.extend(["-c", "\\COPY {} FROM '{}' WITH (FORMAT CSV, DELIMITER '{}')".format(
        table_name, csv_path, delimiter
    )])

    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        return CommandResult(
            success=proc.returncode == 0,
            output=proc.stdout,
            error=proc.stderr,
            returncode=proc.returncode,
            duration_seconds=time.time() - start,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            error=str(e),
            returncode=-99,
        )


def query(
    sql: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    format: str = "table",
) -> CommandResult:
    """
    Execute a SQL query and return results.

    Args:
        sql: SQL query
        format: Output format ('table', 'csv', 'json')

    Returns:
        CommandResult
    """
    if os.environ.get("TIMESCALEDB_MOCK"):
        return CommandResult(
            success=True,
            output="Mock query result for: {}".format(sql[:50]),
            returncode=0,
        )

    extra = []
    if format == "csv":
        extra = ["--csv"]
    elif format == "json":
        extra = ["-At", "-c", "SELECT json_agg(row_to_json(t)) FROM ({}) t".format(sql.replace(";", ""))]
        sql = "SELECT json_agg(row_to_json(t)) FROM ({}) t".format(sql.replace(";", ""))

    return _run_sql(sql, host, port, user, password, dbname, extra_args=extra if extra else None)


# -------------------------------------------------------------------
# Retention policy
# -------------------------------------------------------------------

def set_retention_policy(
    table_name: str,
    interval: str,
    drop_from_chunks: bool = True,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> CommandResult:
    """Set a data retention policy on a hypertable."""
    if os.environ.get("TIMESCALEDB_MOCK"):
        return CommandResult(
            success=True,
            output="Retention policy set: {} on {}".format(interval, table_name),
            returncode=0,
        )

    drop_clause = "drop_from_chunks => true" if drop_from_chunks else "drop_from_chunks => false"
    sql = (
        "SELECT add_retention_policy('{}', interval '{}', {});"
    ).format(table_name, interval, drop_clause)

    return _run_sql(sql, host, port, user, password, dbname, timeout=60, check=False)


# -------------------------------------------------------------------
# Stats
# -------------------------------------------------------------------

def get_database_stats(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
) -> dict:
    """Get overall database statistics."""
    if os.environ.get("TIMESCALEDB_MOCK"):
        return {
            "success": True,
            "hypertables": 3,
            "continuous_aggregates": 1,
            "total_rows": 1500000,
            "database_size": "256 MB",
        }

    queries = {
        "hypertables": (
            "SELECT COUNT(*) FROM timescaledb_information.hypertables;"
        ),
        "continuous_aggregates": (
            "SELECT COUNT(*) FROM timescaledb_information.continuous_aggregates;"
        ),
        "database_size": (
            "SELECT pg_size_pretty(pg_database_size(current_database()));"
        ),
    }

    results = {}
    for key, sql in queries.items():
        r = _run_sql(sql, host, port, user, password, dbname, timeout=10, check=False)
        if r.success:
            results[key] = r.output.strip()

    return {"success": True, **results}
