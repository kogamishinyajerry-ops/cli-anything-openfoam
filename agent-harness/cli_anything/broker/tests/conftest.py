"""pytest configuration for broker tests - enable mock by default."""
import os
os.environ.setdefault("BROKER_MOCK", "1")
