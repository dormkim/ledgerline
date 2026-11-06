import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["LLM_DISABLED"] = "1"  # tests never call a paid endpoint; LLM paths are tested with a fake
