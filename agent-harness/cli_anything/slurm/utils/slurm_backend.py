"""
slurm_backend.py - Slurm Workload Manager / PBS Pro CLI wrapper

Wraps Slurm and PBS/Torque commands for HPC cluster job management.

Slurm commands:
  - sbatch <script>       Submit job script
  - squeue [-u user]      List jobs in queue
  - scancel <jobid>       Cancel a job
  - sinfo [-N]            Show node info
  - scontrol show job     Job details
  - sview                 GUI (not CLI)

PBS commands (Torque/Altair):
  - qsub <script>         Submit job script
  - qstat [-u user]       List jobs
  - qdel <jobid>          Delete job
  - pbsnodes [-a]         Show node info
  - qhold <jobid>         Hold a job
  - qrls <jobid>          Release held job

Install:
  - Slurm: provided by cluster admin (slurm.conf, srun, sbatch)
  - PBS: sudo apt install torque-pbs (Linux) / build from source (macOS)

Principles:
  - MUST call real scheduler commands, not reimplement
  - Scheduler is HARD dependency - error clearly if not found
  - Jobs run on remote cluster, not local machine
  - Supports both Slurm and PBS/Torque schedulers
"""

from __future__ import annotations

import datetime
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

SLURM_VERSION = "1.0.0"


# -------------------------------------------------------------------
# Scheduler detection
# -------------------------------------------------------------------

def detect_scheduler() -> str:
    """
    Detect available scheduler.

    Returns: 'slurm', 'pbs', or 'none'
    """
    if os.environ.get("SLURM_MOCK") or os.environ.get("PBS_MOCK"):
        return "mock"

    for cmd in ["sbatch", "squeue"]:
        try:
            r = subprocess.run(["which", cmd], capture_output=True, timeout=5)
            if r.returncode == 0:
                return "slurm"
        except Exception:
            pass

    for cmd in ["qsub", "qstat"]:
        try:
            r = subprocess.run(["which", cmd], capture_output=True, timeout=5)
            if r.returncode == 0:
                return "pbs"
        except Exception:
            pass

    return "none"


def get_scheduler() -> str:
    """Get scheduler type, raises if none found."""
    sched = os.environ.get("SCHEDULER_TYPE", "").lower()
    if sched in ("slurm", "pbs", "mock"):
        return sched

    detected = detect_scheduler()
    if detected == "none":
        raise RuntimeError(
            "No HPC scheduler found (Slurm or PBS).\n"
            "Set SCHEDULER_TYPE=slurm or SCHEDULER_TYPE=pbs to specify.\n"
            "Or run on an HPC cluster with Slurm/PBS installed."
        )
    return detected


# -------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------

@dataclass
class CommandResult:
    """Result of a scheduler command execution."""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int = 0
    duration_seconds: float = 0.0


# -------------------------------------------------------------------
# Core runner
# -------------------------------------------------------------------

def _run(cmd: list, timeout: int = 60, check: bool = True) -> CommandResult:
    """Run a scheduler command."""
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
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
            error="Command timed out after {}s".format(timeout),
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
# Slurm commands
# -------------------------------------------------------------------

def slurm_submit(
    script_path: str,
    nodes: int = 1,
    ntasks: int = 1,
    cpus_per_task: int = 1,
    mem: str = "4G",
    time_limit: str = "1:00:00",
    partition: Optional[str] = None,
    job_name: Optional[str] = None,
    output: Optional[str] = None,
    error: Optional[str] = None,
    extra_args: Optional[list] = None,
) -> CommandResult:
    """
    Submit a job to Slurm.

    Args:
        script_path: Path to job script
        nodes: Number of nodes
        ntasks: Number of tasks
        cpus_per_task: CPUs per task
        mem: Memory per node (e.g. '4G', '8000M')
        time_limit: Time limit (HH:MM:SS)
        partition: Partition name
        job_name: Job name
        output: Output file path
        error: Error file path
        extra_args: Additional sbatch arguments

    Returns:
        CommandResult with job_id
    """
    script = Path(script_path)
    if not script.exists():
        return CommandResult(success=False, error="Script not found: {}".format(script), returncode=1)

    if os.environ.get("SLURM_MOCK"):
        return CommandResult(
            success=True,
            output="Submitted batch job 12345",
            returncode=0,
        )

    cmd = ["sbatch"]
    cmd.extend([
        "--nodes={}".format(nodes),
        "--ntasks={}".format(ntasks),
        "--cpus-per-task={}".format(cpus_per_task),
        "--mem={}".format(mem),
        "--time={}".format(time_limit),
    ])
    if partition:
        cmd.extend(["--partition", partition])
    if job_name:
        cmd.extend(["--job-name", job_name])
    if output:
        cmd.extend(["--output", output])
    if error:
        cmd.extend(["--error", error])
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(str(script))

    return _run(cmd, timeout=30, check=False)


def slurm_list_jobs(user: Optional[str] = None, state: Optional[str] = None) -> CommandResult:
    """
    List Slurm jobs.

    Args:
        user: Username (default: current user)
        state: Filter by state (RUNNING, PENDING, etc.)

    Returns:
        CommandResult with job list
    """
    if os.environ.get("SLURM_MOCK"):
        mock_output = (
            "JOBID PARTITION NAME USER ST TS\n"
            "12345 compute myjob user R 12:00\n"
            "12346 compute myjob2 user PD 0:01"
        )
        return CommandResult(success=True, output=mock_output, returncode=0)

    cmd = ["squeue", "--format=%i %P %j %u %T %M"]
    if user:
        cmd.extend(["--user", user])
    if state:
        cmd.extend(["--state", state])

    return _run(cmd, timeout=15, check=False)


def slurm_cancel(job_id: str) -> CommandResult:
    """Cancel a Slurm job."""
    if os.environ.get("SLURM_MOCK"):
        return CommandResult(success=True, output="Cancelled job {}".format(job_id), returncode=0)

    result = _run(["scancel", str(job_id)], timeout=10, check=False)
    if result.success:
        result.output = "Cancelled job {}".format(job_id)
    return result


def slurm_node_info() -> CommandResult:
    """Get Slurm node information."""
    if os.environ.get("SLURM_MOCK"):
        return CommandResult(
            success=True,
            output="NODELIST PARTITION STATUS\n"
                   "node001 compute IDLE\n"
                   "node002 compute MIXED\n"
                   "node003 compute DOWN",
            returncode=0,
        )

    return _run(["sinfo", "-N", "--format=%N %P %a %c %m %e"], timeout=15, check=False)


def slurm_job_info(job_id: str) -> dict:
    """
    Get detailed Slurm job information.

    Returns dict with job details.
    """
    if os.environ.get("SLURM_MOCK"):
        return {
            "success": True,
            "job_id": job_id,
            "job_name": "mock_job",
            "user": "testuser",
            "state": "RUNNING",
            "partition": "compute",
            "nodes": 1,
            "ntasks": 4,
            "time_used": "00:15:32",
            "time_limit": "01:00:00",
        }

    result = _run(["scontrol", "show", "job", str(job_id)], timeout=15, check=False)
    if not result.success:
        return {"success": False, "error": result.error}

    info = {"success": True, "job_id": job_id}

    # Parse scontrol output
    for line in result.output.split("\n"):
        for field in ["JobName", "UserId", "JobState", "Partition", "NumNodes", "NumTasks",
                       "TimeUsed", "TimeLimit", "WorkDir", "StdOut"]:
            if field + "=" in line:
                val = line.split(field + "=")[1].split()[0] if field + "=" in line else ""
                key = field.lower()
                info[key] = val

    return info


# -------------------------------------------------------------------
# PBS commands
# -------------------------------------------------------------------

def pbs_submit(
    script_path: str,
    nodes: int = 1,
    ppn: int = 1,
    walltime: str = "1:00:00",
    queue: Optional[str] = None,
    job_name: Optional[str] = None,
    output: Optional[str] = None,
    error: Optional[str] = None,
) -> CommandResult:
    """
    Submit a job to PBS.

    Args:
        script_path: Path to job script
        nodes: Number of nodes
        ppn: Processors per node
        walltime: Time limit (HH:MM:SS)
        queue: Queue name
        job_name: Job name
        output: Output file path
        error: Error file path

    Returns:
        CommandResult with job_id
    """
    if os.environ.get("PBS_MOCK"):
        return CommandResult(
            success=True,
            output="12345.server",
            returncode=0,
        )

    script = Path(script_path)
    if not script.exists():
        return CommandResult(success=False, error="Script not found: {}".format(script), returncode=1)

    args = ["qsub"]
    if job_name:
        args.extend(["-N", job_name])
    if nodes or ppn:
        args.extend(["-l", "nodes={}:ppn={}".format(nodes, ppn)])
    if walltime:
        args.extend(["-l", "walltime={}".format(walltime)])
    if queue:
        args.extend(["-q", queue])
    if output:
        args.extend(["-o", output])
    if error:
        args.extend(["-e", error])
    args.append(str(script))

    return _run(args, timeout=30, check=False)


def pbs_list_jobs(user: Optional[str] = None) -> CommandResult:
    """List PBS jobs."""
    if os.environ.get("PBS_MOCK"):
        return CommandResult(
            success=True,
            output="Req'd  Req'd  Elap\n"
                   "Job ID          Username Queue    Name    SessID NDS TSK Memory Time  S Time\n"
                   "12345.server    user     compute myjob    --      1  4  4gb 01:00 R 00:15",
            returncode=0,
        )

    cmd = ["qstat"]
    if user:
        cmd.extend(["-u", user])

    return _run(cmd, timeout=15, check=False)


def pbs_cancel(job_id: str) -> CommandResult:
    """Cancel a PBS job."""
    if os.environ.get("PBS_MOCK"):
        return CommandResult(success=True, output="Deleted job {}".format(job_id), returncode=0)

    result = _run(["qdel", str(job_id)], timeout=10, check=False)
    if result.success:
        result.output = "Deleted job {}".format(job_id)
    return result


def pbs_node_info() -> CommandResult:
    """Get PBS node information."""
    if os.environ.get("PBS_MOCK"):
        return CommandResult(
            success=True,
            output="server = server\n"
                   "node node001\n"
                   "    state = free\n"
                   "    np = 32\n"
                   "node node002\n"
                   "    state = job-exclusive\n"
                   "    np = 32",
            returncode=0,
        )

    return _run(["pbsnodes", "-a"], timeout=15, check=False)


# -------------------------------------------------------------------
# Generic wrappers (auto-detect scheduler)
# -------------------------------------------------------------------

def submit_job(
    script_path: str,
    nodes: int = 1,
    ntasks: int = 1,
    cpus_per_task: int = 1,
    mem: str = "4G",
    time_limit: str = "1:00:00",
    partition: Optional[str] = None,
    job_name: Optional[str] = None,
) -> CommandResult:
    """
    Submit a job (auto-detects scheduler).

    Uses SLURM_MOCK or PBS_MOCK env var for testing.
    """
    if os.environ.get("SLURM_MOCK"):
        return slurm_submit(script_path, nodes, ntasks, cpus_per_task, mem, time_limit, partition, job_name)
    if os.environ.get("PBS_MOCK"):
        return pbs_submit(script_path, nodes, cpus_per_task, time_limit, queue=partition, job_name=job_name)

    sched = get_scheduler()
    if sched == "slurm":
        return slurm_submit(script_path, nodes, ntasks, cpus_per_task, mem, time_limit, partition, job_name)
    elif sched == "pbs":
        return pbs_submit(script_path, nodes, ntasks, time_limit, queue=partition, job_name=job_name)
    else:
        return CommandResult(success=False, error="No scheduler available", returncode=1)


def list_jobs(user: Optional[str] = None) -> CommandResult:
    """List jobs (auto-detects scheduler)."""
    if os.environ.get("SLURM_MOCK"):
        return slurm_list_jobs(user)
    if os.environ.get("PBS_MOCK"):
        return pbs_list_jobs(user)

    sched = get_scheduler()
    if sched == "slurm":
        return slurm_list_jobs(user)
    elif sched == "pbs":
        return pbs_list_jobs(user)
    else:
        return CommandResult(success=False, error="No scheduler available", returncode=1)


def cancel_job(job_id: str) -> CommandResult:
    """Cancel a job (auto-detects scheduler)."""
    if os.environ.get("SLURM_MOCK"):
        return slurm_cancel(job_id)
    if os.environ.get("PBS_MOCK"):
        return pbs_cancel(job_id)

    sched = get_scheduler()
    if sched == "slurm":
        return slurm_cancel(job_id)
    elif sched == "pbs":
        return pbs_cancel(job_id)
    else:
        return CommandResult(success=False, error="No scheduler available", returncode=1)


def get_version() -> dict:
    """Get scheduler version info."""
    if os.environ.get("SLURM_MOCK"):
        return {"success": True, "scheduler": "slurm", "version": "23.02.0"}
    if os.environ.get("PBS_MOCK"):
        return {"success": True, "scheduler": "pbs", "version": "20.0.0"}

    sched = detect_scheduler()
    if sched == "none":
        return {"success": False, "error": "No scheduler found"}

    try:
        if sched == "slurm":
            r = subprocess.run(["sbatch", "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                v = r.stdout.strip().split()[-1] if r.stdout else "unknown"
                return {"success": True, "scheduler": "slurm", "version": v}
        elif sched == "pbs":
            r = subprocess.run(["qstat", "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return {"success": True, "scheduler": "pbs", "version": "unknown"}
    except Exception:
        pass

    return {"success": False, "error": "Failed to get version"}
