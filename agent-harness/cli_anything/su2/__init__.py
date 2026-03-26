"""
cli_anything.su2 - SU2 CFD CLI harness

Wraps real SU2 v8.4.0 commands (SU2_CFD, SU2_DEF, SU2_DOT, SU2_GEO,
shape_optimization.py, compute_polar.py) for use by the cli-anything harness.

Principles (from HARNESS.md):
- MUST call the real SU2 commands, not reimplement
- Software is a HARD dependency - error clearly if not found
- Always verify output (not just exit 0)
"""

from .su2_cli import main

__all__ = ["main"]
__version__ = "1.0.0"
