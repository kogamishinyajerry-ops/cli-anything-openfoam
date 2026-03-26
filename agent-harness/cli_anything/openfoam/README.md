# OpenFOAM CLI — cli-anything-openfoam

OpenFOAM CFD simulation workflow CLI. Control OpenFOAM from any AI agent via
standardized commands.

## Dependencies

- **Python 3.10+**
- **OpenFOAM** — `apt install openfoam` (Ubuntu/Debian) or from openfoam.org

**Important:** OpenFOAM is a **hard dependency**. Source it before use:
```bash
source /opt/openfoam10/etc/bashrc
```

## Installation

```bash
# From source
cd cli-anything-openfoam/agent-harness
pip install -e .

# Verify
which cli-anything-openfoam
cli-anything-openfoam --help
```

## Quick Start

```bash
# Create case
cli-anything-openfoam case new --name motorBike --template simpleFoam

# Set boundary conditions
cli-anything-openfoam setup boundary --patch inlet --type fixedValue --value "10 0 0" --field U
cli-anything-openfoam setup boundary --patch outlet --type zeroGradient --field p

# Set turbulence
cli-anything-openfoam setup properties --turbulence kEpsilon --nu 1e-5

# Generate mesh
cli-anything-openfoam mesh generate --method blockmesh --project ./motorBike

# Check mesh quality
cli-anything-openfoam mesh check --project ./motorBike

# Run solver
cli-anything-openfoam solve run --solver simpleFoam --end-time 500 --project ./motorBike

# Check status
cli-anything-openfoam solve status --project ./motorBike

# Extract results
cli-anything-openfoam postprocess extract --field U --patch inlet --time 500 --project ./motorBike
```

## Command Groups

| Group | Commands |
|-------|----------|
| `case` | new, info, validate, list |
| `mesh` | generate, check |
| `setup` | boundary, properties, schemes, solvers |
| `solve` | run, status, stop |
| `postprocess` | extract, fields |

## JSON Output

All commands support `--json` for machine-readable output:

```bash
cli-anything-openfoam --json case info --project ./motorBike
```

## Testing

```bash
cd cli-anything-openfoam/agent-harness
python -m pytest cli_anything/openfoam/tests/ -v
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/openfoam/tests/ -v -s
```

## OpenFOAM Version

Automatically detects: v2312, v2406, v10, v2412.
