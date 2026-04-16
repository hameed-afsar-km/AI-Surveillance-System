
import requests
import time

def test_single_frame():
    url = "http://localhost:5050/video_feed"
    try:
        print(f"Connecting to {url}...")
        r = requests.get(url, stream=True, timeout=5)
        if r.status_code != 200:
            print(f"Status code: {r.status_code}")
            return
            
        print("Waiting for first frame...")
        start_time = time.time()
        for chunk in r.iter_content(chunk_size=1024):
            if b'--frame' in chunk:
                print(f"Found boundary after {time.time() - start_time:.2f}s")
                return True
            if time.time() - start_time > 10:
                print("Timed out waiting for frame boundary.")
                break
    except Exception as e:
        print(f"Error: {e}")
    return False

if __name__ == "__main__":
    test_single_frame()
