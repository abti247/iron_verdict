import sys
import os

# Ensure this worktree's src takes precedence over the editable install
# pointing at the main project (shared .venv).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
