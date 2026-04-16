import sys
from unittest.mock import MagicMock

print("DEBUG: Mocking modules...")
sys.modules['ultralytics'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['deep_sort_realtime'] = MagicMock()
sys.modules['deep_sort_realtime.deepsort_tracker'] = MagicMock()

print("DEBUG: Importing app...")
import app
print("DEBUG: App imported.")

if __name__ == "__main__":
    print("Starting MOCKED backend...")
    app.app.run(host="0.0.0.0", port=5050, debug=False)
