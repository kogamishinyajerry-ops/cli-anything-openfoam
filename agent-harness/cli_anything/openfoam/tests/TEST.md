# OpenFOAM CLI - Test Plan & Results

## Test Inventory

- `test_core.py`: Unit tests (synthetic data, no OpenFOAM required)
- `test_full_e2e.py`: E2E tests (require real OpenFOAM installation)

---

## Test Plan

### Unit Tests (`test_core.py`)

#### dict_parser.py
| Test | What it covers | Count |
|------|---------------|-------|
| `test_read_simple_dict` | Parsing basic key-value pairs | 1 |
| `test_read_nested_dict` | Nested brace blocks, solver entries | 1 |
| `test_read_vector_format` | `(x y z)` vector notation | 1 |
| `test_write_then_read_roundtrip` | write_dict → read_dict fidelity | 1 |
| `test_write_nested_roundtrip` | Complex nested dict roundtrip | 1 |
| `test_patch_dict` | Partial update preserves other keys | 1 |
| `test_substitute_vars` | #VAR# replacement | 1 |
| `test_cas_templates_exist` | All solver templates defined | 1 |

#### openfoam_backend.py parsers
| Test | What it covers | Count |
|------|---------------|-------|
| `test_parse_residuals_simple` | Realistic solver output | 1 |
| `test_parse_residuals_empty` | No residuals in log | 1 |
| `test_parse_final_time` | Extract last Time = | 1 |
| `test_parse_final_time_none` | Empty log | 1 |
| `test_parse_checkmesh_quality` | Mesh quality metrics | 1 |
| `test_parse_checkmesh_quality_minimal` | Minimal checkMesh output | 1 |

#### Case structure (CLI)
| Test | What it covers | Count |
|------|---------------|-------|
| `test_case_new_creates_structure` | All directories and files created | 1 |
| `test_case_new_icofoam` | Template selection | 1 |
| `test_case_validate_valid` | Valid case reports "valid" | 1 |
| `test_case_validate_missing_file` | Reports specific issues | 1 |
| `test_case_info` | JSON info output | 1 |
| `test_setup_boundary_modifies_field` | Boundary patch update | 1 |
| `test_setup_properties_writes_files` | turbulenceProperties written | 1 |
| `test_solve_status_no_time_dirs` | Status when not run | 1 |

#### CLI subprocess
| Test | What it covers | Count |
|------|---------------|-------|
| `test_help` | --help flag | 1 |
| `test_case_new_json` | JSON output mode | 1 |
| `test_case_info_json` | Info JSON mode | 1 |

**Unit Test Total: 19**

---

### E2E Tests (`test_full_e2e.py`) — Requires real OpenFOAM

#### Native (no real OpenFOAM commands)
| Test | What it covers | Count |
|------|---------------|-------|
| `test_case_new_all_templates` | simpleFoam, icoFoam, pimpleFoam | 3 |
| `test_boundary_yaml_config` | YAML boundary config roundtrip | 1 |
| `test_parameters_substitution` | #var# in case files | 1 |
| `test_parallel_decomp_dict` | decomposeParDict created | 1 |

#### True Backend (real OpenFOAM commands)
| Test | What it covers | Count |
|------|---------------|-------|
| `test_blockmesh_simple_cube` | blockMesh on cube | 1 |
| `test_checkmesh_quality` | checkMesh quality output | 1 |
| `test_simplefoam_short_run` | simpleFoam 10 iterations | 1 |
| `test_latest_time_detection` | Time directory detection | 1 |
| `test_full_workflow` | case → mesh → solve → extract | 1 |

**E2E Test Total: 10**

**Grand Total: 29 tests planned**

---

## E2E Test Plan

### Workflow Scenarios

#### Scenario 1: Steady-State External Flow
```
Simulates: Simple airfoil external flow
Operations:
  1. case new --name airfoil --template simpleFoam
  2. setup boundary --patch inlet --type fixedValue --value "10 0 0"
  3. mesh generate --method blockmesh
  4. solve run --solver simpleFoam --endTime 100
  5. postprocess extract --field U --patch inlet --operator average
Verified:
  - controlDict written correctly
  - mesh exists (cells > 0)
  - solver runs (residuals logged)
  - field extraction succeeds
```

#### Scenario 2: Transient Laminar Flow
```
Simulates: Cylinder wake (Karman vortex street)
Operations:
  1. case new --name cylinder --template icoFoam
  2. mesh generate --method blockmesh
  3. solve run --solver icoFoam --deltaT 0.001 --endTime 2.0
  4. solve status
Verified:
  - icoFoam template
  - Time advances (0 → 2)
  - Multiple time directories created
```

---

## Test Results

### Running Tests

```bash
# Unit tests (no OpenFOAM required)
cd openfoam/agent-harness
python -m pytest cli_anything/openfoam/tests/test_core.py -v

# E2E tests (requires OpenFOAM)
source /opt/openfoam10/etc/bashrc
python -m pytest cli_anything/openfoam/tests/test_full_e2e.py -v

# Force-installed mode
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/openfoam/tests/ -v -s
```

### Results Summary

```
test_core.py::TestDictParser::test_read_simple_dict                 PASSED
test_core.py::TestDictParser::test_read_nested_dict                  PASSED
test_core.py::TestDictParser::test_read_vector_format                PASSED
test_core.py::TestDictParser::test_write_then_read_roundtrip         PASSED
test_core.py::TestDictParser::test_write_nested_roundtrip            PASSED
test_core.py::TestDictParser::test_patch_dict                        PASSED
test_core.py::TestDictParser::test_substitute_vars                    PASSED
test_core.py::TestDictParser::test_cas_templates_exist               PASSED
test_core.py::TestBackendParsers::test_parse_residuals_simple         PASSED
test_core.py::TestBackendParsers::test_parse_residuals_empty          PASSED
test_core.py::TestBackendParsers::test_parse_final_time               PASSED
test_core.py::TestBackendParsers::test_parse_final_time_none          PASSED
test_core.py::TestBackendParsers::test_parse_checkmesh_quality        PASSED
test_core.py::TestBackendParsers::test_parse_checkmesh_quality_minimal PASSED
test_core.py::TestCaseStructure::test_case_new_creates_structure       PASSED
test_core.py::TestCaseStructure::test_case_new_icofoam                 PASSED
test_core.py::TestCaseStructure::test_case_validate_valid              PASSED
test_core.py::TestCaseStructure::test_case_validate_missing_file       PASSED
test_core.py::TestCaseStructure::test_case_info                        PASSED
test_core.py::TestCaseStructure::test_setup_boundary_modifies_field     PASSED
test_core.py::TestCaseStructure::test_setup_properties_writes_files     PASSED
test_core.py::TestCaseStructure::test_solve_status_no_time_dirs        PASSED
test_core.py::TestCLISubprocess::test_help                            PASSED
test_core.py::TestCLISubprocess::test_case_new_json                    PASSED
test_core.py::TestCLISubprocess::test_case_info_json                  PASSED

================================ 25 passed ===================================
(E2E tests require OpenFOAM installation — run with source /opt/openfoam10/etc/bashrc)
```
