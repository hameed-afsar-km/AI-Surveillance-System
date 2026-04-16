
import requests
import time

def test_feed():
    url = "http://localhost:5050/video_feed"
    try:
        print(f"Connecting to {url}...")
        response = requests.get(url, stream=True, timeout=5)
        if response.status_code == 200:
            print("Successfully connected to stream.")
            count = 0
            for chunk in response.iter_content(chunk_size=1024):
                count += 1
                if count > 10:
                    print("Received data chunks correctly.")
                    return True
        else:
            print(f"Failed to connect. Status: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    return False

if __name__ == "__main__":
    # First check health
    try:
        h = requests.get("http://localhost:5050/health", timeout=2).json()
        print(f"Health: {h}")
    except:
        print("Backend health check failed.")
        
    # Check status
    try:
        s = requests.get("http://localhost:5050/status", timeout=2).json()
        print(f"Status: {s}")
        if not s.get("running"):
            print("System not running. Attempting to start...")
            start = requests.post("http://localhost:5050/start", json={"mode": "webcam"}, timeout=5).json()
            print(f"Start Response: {start}")
            time.sleep(2)
    except Exception as e:
        print(f"Status/Start check failed: {e}")

    test_feed()
