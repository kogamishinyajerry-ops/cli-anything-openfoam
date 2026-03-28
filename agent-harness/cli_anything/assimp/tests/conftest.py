"""pytest configuration for assimp tests - enable mock by default."""
import os
os.environ.setdefault("ASSIMP_MOCK", "1")
