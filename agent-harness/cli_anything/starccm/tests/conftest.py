"""pytest configuration for starccm tests - enable mock by default."""
import os
os.environ.setdefault("STARCCM_MOCK", "1")
