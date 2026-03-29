import requests
import wave
import struct

def create_dummy_wav(filename="test.wav"):
    with wave.open(filename, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        # Write 1 second of silence
        for _ in range(16000):
            f.writeframes(struct.pack('h', 0))

def test_transcribe():
    create_dummy_wav()
    url = "http://127.0.0.1:5000/api/transcribe"
    files = {'audio': open('test.wav', 'rb')}
    
    print(f"Sending POST to {url}...")
    try:
        res = requests.post(url, files=files)
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_transcribe()
