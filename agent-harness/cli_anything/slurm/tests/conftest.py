"""pytest configuration for slurm tests - enable mock by default."""
import os
os.environ.setdefault("SLURM_MOCK", "1")
