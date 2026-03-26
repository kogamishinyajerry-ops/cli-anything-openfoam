"""
su2_backend.py - SU2 v8.4.0 CLI wrapper

Wraps real SU2 commands for use by the cli-anything harness.

SU2 installation: /opt/su2/bin/
Key executables:
  SU2_CFD   - main CFD solver
  SU2_DEF   - mesh deformation / shape design
  SU2_DOT   - discrete adjoint
  SU2_GEO   - geometry tool
  SU2_Nastran
  SU2_SOL
Python scripts (need SU2_RUN=/opt/su2/bin env):
  shape_optimization.py
  compute_polar.py
  continuous_adjoint.py
  discrete_adjoint.py
  direct_differentiation.py
  finite_differences.py
"""

from .su2_backend import (
    SU2_INSTALL,
    find_su2,
    CommandResult,
    _run,
    run_cfd,
    run_def,
    run_dot,
    run_geo,
    run_shape_opt,
    run_compute_polar,
    parse_config,
    update_config_params,
)

__all__ = [
    "SU2_INSTALL",
    "find_su2",
    "CommandResult",
    "_run",
    "run_cfd",
    "run_def",
    "run_dot",
    "run_geo",
    "run_shape_opt",
    "run_compute_polar",
    "parse_config",
    "update_config_params",
]
