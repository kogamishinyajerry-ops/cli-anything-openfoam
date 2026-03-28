"""pytest configuration for fastlane tests - enable mock by default."""
import os
os.environ.setdefault("FASTLANE_MOCK", "1")
