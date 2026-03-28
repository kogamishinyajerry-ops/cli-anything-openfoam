"""pytest configuration for quantconnect tests - enable mock by default."""
import os
os.environ.setdefault("QC_MOCK", "1")
