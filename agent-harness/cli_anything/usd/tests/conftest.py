"""pytest configuration for USD tests - enable mock by default."""
import os
os.environ.setdefault("USD_MOCK", "1")
