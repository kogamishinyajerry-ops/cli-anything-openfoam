from __future__ import annotations
"""
dict_parser.py — OpenFOAM dictionary file parser and writer

Reads and writes OpenFOAM dictionary files (*Dict, fvSchemes, fvSolution, etc.)
OpenFOAM format:
    key1  value1;
    key2
    {
        subkey  subvalue;
    }
"""

import re
import shutil
from pathlib import Path
from typing import Any


# -------------------------------------------------------------------
# Tokenizer
# -------------------------------------------------------------------

TK_STRING   = 'STRING'
TK_LBRACE   = 'LBRACE'
TK_RBRACE   = 'RBRACE'
TK_SEMI     = 'SEMI'
TK_LPAREN   = 'LPAREN'
TK_RPAREN   = 'RPAREN'
TK_LBRACKET = 'LBRACKET'
TK_RBRACKET = 'RBRACKET'
TK_NUMBER   = 'NUMBER'
TK_WORD     = 'WORD'
TK_DOLLAR   = 'DOLLAR'
TK_HASH     = 'HASH'


def _tokenize(text: str):
    """Tokenize OpenFOAM dictionary into (type, value) pairs."""
    # Strip comments
    text = re.sub(r'//.*', '', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    tokens = []
    i, n = 0, len(text)

    while i < n:
        ch = text[i]

        if ch.isspace():
            i += 1; continue

        if ch == '"':
            j = i + 1
            while j < n:
                if text[j] == '\\': j += 2
                elif text[j] == '"': j += 1; break
                else: j += 1
            tokens.append((TK_STRING, text[i:j])); i = j; continue

        if ch == "'":
            j = i + 1
            while j < n and text[j] != "'": j += 1
            tokens.append((TK_STRING, text[i:j+1])); i = j + 1; continue

        if ch == '{': tokens.append((TK_LBRACE, ch)); i += 1; continue
        if ch == '}': tokens.append((TK_RBRACE, ch)); i += 1; continue
        if ch == ';': tokens.append((TK_SEMI, ch)); i += 1; continue
        if ch == '(': tokens.append((TK_LPAREN, ch)); i += 1; continue
        if ch == ')': tokens.append((TK_RPAREN, ch)); i += 1; continue
        if ch == '[': tokens.append((TK_LBRACKET, ch)); i += 1; continue
        if ch == ']': tokens.append((TK_RBRACKET, ch)); i += 1; continue

        if ch == '#':
            j = i + 1
            while j < n and text[j].isalnum(): j += 1
            tokens.append((TK_HASH, text[i:j])); i = j; continue

        if ch == '$':
            j = i + 1
            if j < n and text[j] == '{':
                j += 1
                while j < n and text[j] != '}': j += 1
                tokens.append((TK_DOLLAR, text[i:j+1])); i = j + 1
            else:
                while j < n and (text[j].isalnum() or text[j] == '_'): j += 1
                tokens.append((TK_DOLLAR, text[i:j])); i = j
            continue

        # Number
        if ch.isdigit() or (ch in '+-' and i + 1 < n and text[i+1].isdigit()):
            j = i
            if text[j] in '+-': j += 1
            while j < n and text[j].isdigit(): j += 1
            if j < n and text[j] == '.': j += 1
            while j < n and text[j].isdigit(): j += 1
            if j < n and text[j] in 'eE':
                j += 1
                if j < n and text[j] in '+-': j += 1
                while j < n and text[j].isdigit(): j += 1
            num_str = text[i:j]
            try:
                num_str = str(int(num_str)) if '.' not in num_str and 'e' not in num_str.lower() else str(float(num_str))
            except ValueError:
                pass
            tokens.append((TK_NUMBER, num_str)); i = j; continue

        # Word
        if ch.isalpha() or ch == '_':
            j = i
            while j < n and (text[j].isalnum() or text[j] == '_'): j += 1
            tokens.append((TK_WORD, text[i:j])); i = j; continue

        i += 1

    return tokens


# -------------------------------------------------------------------
# Parser
# -------------------------------------------------------------------

class DictParser:
    """Parse token stream into Python dict."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return ('EOF', '')

    def consume(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def at_end(self):
        return self.peek()[0] == 'EOF'

    def parse_value(self):
        kind, val = self.peek()

        if kind == TK_NUMBER:
            self.consume()
            try:
                return int(val) if '.' not in val and 'e' not in val.lower() else float(val)
            except ValueError:
                return val

        if kind == TK_STRING:
            self.consume()
            return val.strip('"\'')

        if kind == TK_WORD:
            self.consume()
            return val

        if kind in (TK_DOLLAR, TK_HASH):
            self.consume()
            return val  # preserve reference

        return None

    def parse_list(self, open_tok, close_tok):
        """Parse (...) or [...] list."""
        self.consume()  # consume open
        items = []
        while self.peek()[0] != close_tok and self.peek()[0] != 'EOF':
            items.append(self.parse_value())
        if self.peek()[0] == close_tok:
            self.consume()
        return items

    def parse_block(self):
        """Parse { ... } block into dict. Assumes opening { has been consumed."""
        result = {}
        while self.peek()[0] not in (TK_RBRACE, 'EOF'):
            kind, key = self.peek()

            if kind == TK_RBRACE:
                break

            if kind == TK_WORD:
                self.consume()  # consume key
                nk = self.peek()[0]

                if nk == TK_LBRACE:
                    # key { ... }
                    self.consume()  # consume {
                    result[key] = self.parse_block()
                elif nk == TK_SEMI:
                    # key;  (boolean/marker)
                    self.consume()
                    result[key] = True
                elif nk == TK_LPAREN:
                    result[key] = self.parse_list(TK_LPAREN, TK_RPAREN)
                    if self.peek()[0] == TK_SEMI:
                        self.consume()
                elif nk == TK_LBRACKET:
                    result[key] = self.parse_list(TK_LBRACKET, TK_RBRACKET)
                    if self.peek()[0] == TK_SEMI:
                        self.consume()
                else:
                    # key  value;
                    val = self.parse_value()
                    result[key] = val
                    if self.peek()[0] == TK_SEMI:
                        self.consume()

            elif kind == TK_LBRACE:
                # Naked { block at top level of this block (possible for empty dicts)
                self.consume()
                self.parse_block()
            else:
                # Skip unknown
                self.consume()

        if self.peek()[0] == TK_RBRACE:
            self.consume()

        return result

    def parse(self):
        """Parse tokens as a dictionary block (starting with { or bare keys).

        Skips any leading FoamFile { ... } header block, which is the standard
        OpenFOAM file header and not part of the actual dictionary content.
        """
        # Skip optional FoamFile header block: "FoamFile { ... }"
        if (self.peek()[0] == TK_WORD and self.peek()[1] == 'FoamFile'
                and self.peek(1)[0] == TK_LBRACE):
            self.consume()  # consume 'FoamFile'
            self.consume()  # consume '{'
            depth = 1
            while depth > 0 and not self.at_end():
                tok = self.consume()
                if tok[0] == TK_LBRACE:
                    depth += 1
                elif tok[0] == TK_RBRACE:
                    depth -= 1
        if self.peek()[0] == TK_LBRACE:
            self.consume()
            return self.parse_block()
        return self.parse_block()


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def read_dict(path: Path) -> dict:
    """Read an OpenFOAM dictionary file and return Python dict."""
    text = path.read_text()
    tokens = _tokenize(text)
    return DictParser(tokens).parse()


def write_dict(path: Path, data: dict, foam_file_header: bool = True) -> None:
    """Write a Python dict to an OpenFOAM dictionary file."""
    lines = []

    if foam_file_header:
        # OpenFOAM's dictionary parser does NOT handle multi-line C comments
        # (/* */), only single-line // comments. Only emit FoamFile header.
        lines.append("FoamFile")
        lines.append("{")
        lines.append("    version     2.0;")
        lines.append("    format      ascii;")
        lines.append("    class       dictionary;")
        lines.append(f"    object      {path.name};")
        lines.append("}")
        lines.append("")

    def serialize(d, indent=0):
        prefix = "    " * indent
        out = []
        for k, v in d.items():
            if isinstance(v, dict):
                if not v:
                    out.append(f"{prefix}{k};")
                else:
                    out.append(f"{prefix}{k}")
                    out.append(prefix + "{")
                    out.extend(serialize(v, indent+1))
                    out.append(prefix + "}")
            elif isinstance(v, list):
                inner = "  ".join(str(x) for x in v)
                # dimensionSet uses [ ], not ( )
                if len(v) == 7 and all(isinstance(x, (int, float)) for x in v):
                    out.append(f"{prefix}{k}  [{inner}];")
                else:
                    out.append(f"{prefix}{k}  ({inner});")
            elif isinstance(v, bool):
                out.append(f"{prefix}{k}      {'on' if v else 'off'};")
            elif isinstance(v, str):
                # OpenFOAM values are never quoted in dict files — write as-is.
                # Only exception: strings containing semicolons or braces need quoting.
                if ';' in v or '{' in v or '}' in v:
                    out.append(f"{prefix}{k}      \"{v}\";")
                else:
                    out.append(f"{prefix}{k}      {v};")
            else:
                out.append(f"{prefix}{k}      {v};")
        return out

    lines.extend(serialize(data))
    path.write_text("\n".join(lines) + "\n")


def patch_dict(path: Path, updates: dict) -> None:
    """Partially update a dictionary file, preserving other keys."""
    existing = read_dict(path) if path.exists() else {}
    existing.update(updates)
    write_dict(path, existing)


def substitute_vars(path: Path, var_map: dict) -> None:
    """Replace #var# or ${var} placeholders in a file."""
    text = path.read_text()
    for var, value in var_map.items():
        text = re.sub(rf'#\b{var}\b#', str(value), text)
        text = re.sub(rf'\$\{{\b{var}\b\}}', str(value), text)
        text = re.sub(rf'\$\b{var}\b(?!\w)', str(value), text)
    path.write_text(text)


def substitute_vars_in_text(text: str, var_map: dict) -> str:
    for var, value in var_map.items():
        text = re.sub(rf'#\b{var}\b#', str(value), text)
        text = re.sub(rf'\$\{{\b{var}\b\}}', str(value), text)
        text = re.sub(rf'\$\b{var}\b(?!\w)', str(value), text)
    return text


# -------------------------------------------------------------------
# Case templates
# -------------------------------------------------------------------

CASE_TEMPLATES = {
    "simpleFoam": {
        "controlDict": {
            "application": "simpleFoam",
            "startFrom": "startTime",
            "startTime": 0,
            "stopAt": "endTime",
            "endTime": 1000,
            "deltaT": 1,
            "writeControl": "timeStep",
            "writeInterval": 100,
            "purgeWrite": 0,
            "writeFormat": "ascii",
            "writePrecision": 6,
            "writeCompression": "off",
            "timeFormat": "general",
            "timePrecision": 6,
            "runTimeModifiable": True,
        },
        "fvSchemes": {
            "ddtSchemes": {"default": "steadyState"},
            "gradSchemes": {"default": "Gauss linear"},
            "divSchemes": {"default": "none"},
            "laplacianSchemes": {"default": "Gauss linear corrected"},
            "interpolationSchemes": {"default": "linear"},
            "snGradSchemes": {"default": "corrected"},
        },
        "fvSolution": {
            "solvers": {
                "p": {"solver": "PCG", "preconditioner": "DIC", "tolerance": 1e-6, "relTol": 0.05},
                "U": {"solver": "smoothSolver", "smoother": "GaussSeidel", "tolerance": 1e-6, "relTol": 0.05},
            },
            "SIMPLE": {
                "nCorrectors": 2,
                "nNonOrthogonalCorrectors": 1,
            },
            "relaxationFactors": {
                "fields": {"p": 0.3},
                "equations": {"U": 0.7},
            },
        },
    },
    "icoFoam": {
        "controlDict": {
            "application": "icoFoam",
            "startFrom": "startTime",
            "startTime": 0,
            "stopAt": "endTime",
            "endTime": 1,
            "deltaT": 0.005,
            "writeControl": "timeStep",
            "writeInterval": 20,
            "purgeWrite": 0,
            "writeFormat": "ascii",
            "writePrecision": 6,
            "runTimeModifiable": True,
        },
        "fvSchemes": {
            "ddtSchemes": {"default": "Euler"},
            "gradSchemes": {"default": "Gauss linear"},
            "divSchemes": {"default": "none"},
            "laplacianSchemes": {"default": "Gauss linear"},
        },
        "fvSolution": {
            "solvers": {
                "p": {"solver": "PCG", "preconditioner": "DIC", "tolerance": 1e-6, "relTol": 0},
                "U": {"solver": "GaussSeidel", "tolerance": 1e-6, "relTol": 0},
            },
        },
    },
    "pimpleFoam": {
        "controlDict": {
            "application": "pimpleFoam",
            "startFrom": "startTime",
            "startTime": 0,
            "stopAt": "endTime",
            "endTime": 1,
            "deltaT": 0.001,
            "writeControl": "runTime",
            "writeInterval": 0.05,
            "purgeWrite": 0,
            "writeFormat": "ascii",
            "writePrecision": 6,
            "runTimeModifiable": True,
            "adjustTimeStep": "off",
            "maxCo": 1.0,
        },
        "fvSchemes": {
            "ddtSchemes": {"default": "Euler"},
            "gradSchemes": {"default": "Gauss linear"},
            "divSchemes": {"default": "none"},
            "laplacianSchemes": {"default": "Gauss linear corrected"},
            "interpolationSchemes": {"default": "linear"},
            "snGradSchemes": {"default": "corrected"},
        },
        "fvSolution": {
            "solvers": {
                "p": {"solver": "PCG", "preconditioner": "DIC", "tolerance": 1e-6, "relTol": 0.01},
                "U": {"solver": "smoothSolver", "smoother": "GaussSeidel", "tolerance": 1e-6, "relTol": 0.01},
            },
            "PIMPLE": {"nCorrectors": 2, "nNonOrthogonalCorrectors": 1},
        },
    },
}
