"""
timescaledb_cli.py - Click CLI for cli-anything-timescaledb

Commands:
  hypertable    - Hypertable operations (create, list, info)
  aggregate     - Continuous aggregate operations
  compression   - Compression management
  data          - Data operations (insert, query)
  retention     - Retention policy management
  stats         - Database statistics
  info          - Version info

All commands support --json for machine-readable output.
"""

from __future__ import annotations

import json
from typing import Optional

import click

from .utils import timescaledb_backend as tb

__all__ = ["main"]

JSON_MODE = False


def echo(msg: str, **kwargs) -> None:
    click.echo(msg, err=True, **kwargs)


def success(msg: str) -> None:
    click.echo("[OK] {}".format(msg), err=True)


def error(msg: str) -> None:
    click.echo("[ERROR] {}".format(msg), err=True, color="red")


def json_out(data: dict) -> None:
    click.echo(json.dumps(data, indent=2))


def get_conn_opts(host, port, user, password, dbname):
    """Return connection options dict for backend functions."""
    opts = {}
    if host:
        opts["host"] = host
    if port:
        opts["port"] = port
    if user:
        opts["user"] = user
    if password:
        opts["password"] = password
    if dbname:
        opts["dbname"] = dbname
    return opts


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="JSON output mode")
@click.option("--host", default=None, help="Database host")
@click.option("--port", type=int, default=None, help="Database port")
@click.option("--user", default=None, help="Database user")
@click.option("--password", default=None, help="Database password")
@click.option("--dbname", default=None, help="Database name")
@click.pass_context
def cli(ctx, json_output: bool, host, port, user, password, dbname):
    """TimescaleDB Time-Series Database — manage hypertables, aggregates, and data from CLI.

    TimescaleDB is a PostgreSQL extension for time-series data.
    Supports hypertables, continuous aggregates, compression, and retention policies.

    Examples:
      timescaledb hypertable create --table metrics --time time
      timescaledb hypertable list
      timescaledb data insert --table metrics --csv data.csv
      timescaledb data query "SELECT * FROM metrics LIMIT 10"
      timescaledb compression enable --table metrics
      timescaledb stats
    """
    global JSON_MODE
    JSON_MODE = json_output
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["conn"] = get_conn_opts(host, port, user, password, dbname)

    if ctx.invoked_subcommand is None:
        echo("TimescaleDB harness (CLI wrapper)")
        v = tb.get_version()
        if v.get("success"):
            echo("TimescaleDB: {}".format(v["version"]))
            echo("PostgreSQL: {}".format(v.get("postgres_version", "unknown")))
        else:
            echo("TimescaleDB: not found or not installed")


# ==================================================================
# info command
# ==================================================================

@cli.group("info")
def cmd_info():
    """Version and information."""
    pass


@cmd_info.command("version")
@click.pass_context
def cmd_version(ctx):
    """Show TimescaleDB version."""
    global JSON_MODE
    v = tb.get_version()
    if JSON_MODE:
        json_out(v)
    else:
        if v.get("success"):
            echo("TimescaleDB: {}".format(v["timescaledb_version"]))
            echo("PostgreSQL: {}".format(v.get("postgres_version", "unknown")))
        else:
            error("Failed to get version")


# ==================================================================
# hypertable command
# ==================================================================

@cli.group("hypertable")
def cmd_hypertable():
    """Hypertable operations."""
    pass


@cmd_hypertable.command("create")
@click.option("--table", "-t", required=True, help="Table name (or schema.table)")
@click.option("--time", required=True, help="Time column name")
@click.option("--space", help="Space partitioning column(s)")
@click.option("--chunk", help="Chunk interval (e.g. '1 day', '1 hour')")
@click.pass_context
def cmd_hypertable_create(ctx, table, time, space, chunk):
    """Create a hypertable."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    result = tb.create_hypertable(
        table, time,
        space_columns=space,
        chunk_interval=chunk,
        **conn
    )

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Created hypertable: {}".format(table))
        else:
            error("Failed to create hypertable")
            echo("  {}".format(result.error[:200]))


@cmd_hypertable.command("list")
@click.pass_context
def cmd_hypertable_list(ctx):
    """List all hypertables."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    info = tb.list_hypertables(**conn)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            hts = info.get("hypertables", [])
            echo("Hypertables ({}):".format(len(hts)))
            for ht in hts:
                echo("  {} [schema={}, dims={}, chunks={}]".format(
                    ht["Name"], ht["schema"], ht["dimensions"], ht["chunks"]))
        else:
            error("Failed to list hypertables")


@cmd_hypertable.command("info")
@click.option("--table", "-t", required=True, help="Table name")
@click.pass_context
def cmd_hypertable_info(ctx, table):
    """Get hypertable details."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    info = tb.hypertable_info(table, **conn)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Hypertable: {}".format(info.get("table_name", table)))
            for key, val in info.items():
                if key not in ("success", "table_name", "raw_output"):
                    echo("  {}: {}".format(key, val))
        else:
            error("Failed to get hypertable info")


# ==================================================================
# aggregate command
# ==================================================================

@cli.group("aggregate")
def cmd_aggregate():
    """Continuous aggregate operations."""
    pass


@cmd_aggregate.command("create")
@click.option("--name", "-n", required=True, help="Aggregate view name")
@click.option("--source", "-s", required=True, help="Source hypertable")
@click.option("--bucket", "-b", required=True, help="Time bucket interval (e.g. '1 hour')")
@click.option("--time-col", "-tc", required=True, help="Time column")
@click.option("--group-by", "-g", help="Additional group by columns")
@click.pass_context
def cmd_aggregate_create(ctx, name, source, bucket, time_col, group_by):
    """Create a continuous aggregate."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    result = tb.create_continuous_aggregate(
        name, source, time_col, bucket,
        group_columns=group_by,
        **conn
    )

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Created continuous aggregate: {}".format(name))
        else:
            error("Failed to create aggregate")
            echo("  {}".format(result.error[:200]))


@cmd_aggregate.command("list")
@click.pass_context
def cmd_aggregate_list(ctx):
    """List all continuous aggregates."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    info = tb.list_continuous_aggregates(**conn)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            aggs = info.get("aggregates", [])
            echo("Continuous Aggregates ({}):".format(len(aggs)))
            for agg in aggs:
                echo("  {}: {} (bucket: {})".format(
                    agg["Name"], agg["view_name"], agg["bucket"]))
        else:
            error("Failed to list aggregates")


# ==================================================================
# compression command
# ==================================================================

@cli.group("compression")
def cmd_compression():
    """Compression management."""
    pass


@cmd_compression.command("enable")
@click.option("--table", "-t", required=True, help="Hypertable name")
@click.option("--segment-by", help="Segment by column")
@click.pass_context
def cmd_compression_enable(ctx, table, segment_by):
    """Enable compression on a hypertable."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    result = tb.enable_compression(table, segment_by=segment_by, **conn)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Compression enabled: {}".format(table))
        else:
            error("Failed to enable compression")
            echo("  {}".format(result.error[:200]))


@cmd_compression.command("stats")
@click.pass_context
def cmd_compression_stats(ctx):
    """Show compression statistics."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    info = tb.compression_info(**conn)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Compression Statistics")
            echo("======================")
            echo(info.get("raw_output", ""))
        else:
            error("Failed to get compression stats")


# ==================================================================
# data command
# ==================================================================

@cli.group("data")
def cmd_data():
    """Data operations."""
    pass


@cmd_data.command("insert")
@click.option("--table", "-t", required=True, help="Target table")
@click.option("--csv", "-c", required=True, help="CSV file path")
@click.option("--delimiter", "-d", default=",", help="CSV delimiter")
@click.pass_context
def cmd_data_insert(ctx, table, csv, delimiter):
    """Insert data from CSV into a table."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    result = tb.insert_from_csv(table, csv, delimiter=delimiter, **conn)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Inserted data into: {}".format(table))
            echo("  {}".format(result.output[:200]))
        else:
            error("Insert failed")
            echo("  {}".format(result.error[:200]))


@cmd_data.command("query")
@click.option("--sql", "-s", required=True, help="SQL query")
@click.option("--format", "-f", type=click.Choice(["table", "csv", "json"]),
              default="table", help="Output format")
@click.pass_context
def cmd_data_query(ctx, sql, format):
    """Execute a SQL query."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    result = tb.query(sql, format=format, **conn)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Query executed")
            echo(result.output[:1000])
        else:
            error("Query failed")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# retention command
# ==================================================================

@cli.command("retention")
@click.option("--table", "-t", required=True, help="Hypertable name")
@click.option("--interval", "-i", required=True, help="Retention interval (e.g. '30 days')")
@click.pass_context
def cmd_retention(ctx, table, interval):
    """Set a data retention policy."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    result = tb.set_retention_policy(table, interval, **conn)

    if JSON_MODE:
        json_out({"success": result.success, "output": result.output, "error": result.error})
    else:
        if result.success:
            success("Retention policy set: {} on {}".format(interval, table))
        else:
            error("Failed to set retention policy")
            echo("  {}".format(result.error[:200]))


# ==================================================================
# stats command
# ==================================================================

@cli.command("stats")
@click.pass_context
def cmd_stats(ctx):
    """Show database statistics."""
    global JSON_MODE
    conn = ctx.obj["conn"]

    info = tb.get_database_stats(**conn)

    if JSON_MODE:
        json_out(info)
    else:
        if info.get("success"):
            echo("Database Statistics")
            echo("===================")
            for key, val in info.items():
                if key != "success":
                    echo("  {}: {}".format(key, val))
        else:
            error("Failed to get stats")


# ==================================================================
# Entry point
# ==================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
