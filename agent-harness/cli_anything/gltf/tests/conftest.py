"""pytest configuration for gltf tests - enable mock by default."""
import os
os.environ.setdefault("GLTF_MOCK", "1")
