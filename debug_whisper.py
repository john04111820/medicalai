import whisper
import os
import sys

def test_whisper():
    print(f"Python version: {sys.version}")
    
    # 1. Check FFmpeg
    print("\n[1] Checking FFmpeg...")
    try:
        import shutil
        if shutil.which("ffmpeg"):
            print("FFmpeg found in PATH")
        else:
            print("[FAIL] FFmpeg NOT found in PATH. Whisper requires FFmpeg.")
    except Exception as e:
        print(f"Error checking FFmpeg: {e}")

    # 2. Load Model
    print("\n[2] Loading Whisper model 'base'...")
    try:
        model = whisper.load_model("base")
        print("[PASS] Model loaded successfully")
        
        # 3. Test Transcribe (Dummy)
        # We need a file to test really, but loading is the first step.
        # We can try to generate a dummy file or just skip if no file.
    except Exception as e:
        print(f"[FAIL] Model load failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_whisper()
