# sensor_service.py
import time
import threading

from mpu6050 import mpu6050           # pip install mpu6050-raspberrypi
import sounddevice as sd              # pip install sounddevice
import numpy as np

from notify_v1 import send_alert      # your existing alert function

# --- MOTION SENSOR SETUP ---
motion_sensor    = mpu6050(0x68)
MOTION_THRESHOLD = 0.5   # in g’s
MOTION_COOLDOWN  = 60    # seconds

# --- SOUND SENSOR SETUP ---
SOUND_DURATION   = 0.5      # seconds per read
SOUND_FS         = 16000    # sample rate
SOUND_THRESHOLD  = 0.02     # RMS amplitude
SOUND_COOLDOWN   = 60       # seconds

def motion_loop():
    last = 0
    while True:
        accel = motion_sensor.get_accel_data()
        if (abs(accel['x'])>MOTION_THRESHOLD or
            abs(accel['y'])>MOTION_THRESHOLD or
            abs(accel['z'])>MOTION_THRESHOLD):
            now = time.time()
            if now - last > MOTION_COOLDOWN:
                send_alert("motion", "Motion near car detected!")
                last = now
        time.sleep(0.1)

def sound_loop():
    last = 0
    while True:
        audio = sd.rec(int(SOUND_DURATION*SOUND_FS), samplerate=SOUND_FS, channels=1, blocking=True)
        rms = np.sqrt(np.mean(audio**2))
        if rms > SOUND_THRESHOLD:
            now = time.time()
            if now - last > SOUND_COOLDOWN:
                send_alert("sound", "Suspicious sound detected!")
                last = now
        # tiny sleep to avoid hammering I2S
        time.sleep(0.1)

if __name__ == "__main__":
    # start both loops in background threads
    threading.Thread(target=motion_loop, daemon=True).start()
    threading.Thread(target=sound_loop,  daemon=True).start()

    # keep the main thread alive
    print("Sensor service running. Press Ctrl-C to quit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down sensor service.")
