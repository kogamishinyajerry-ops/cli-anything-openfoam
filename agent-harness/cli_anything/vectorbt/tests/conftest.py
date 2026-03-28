"""pytest configuration for vectorbt tests - enable mock by default."""
import os
os.environ.setdefault("VECTORBT_MOCK", "1")
