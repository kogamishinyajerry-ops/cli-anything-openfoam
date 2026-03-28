"""pytest configuration for elmer tests - enable mock by default."""
import os
os.environ.setdefault("ELMER_MOCK", "1")
