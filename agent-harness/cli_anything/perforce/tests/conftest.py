"""pytest configuration for perforce tests - enable mock by default."""
import os
os.environ.setdefault("P4_MOCK", "1")
