import os
import sys
import argparse
import glob
import time
import threading

import cv2
import numpy as np
from ultralytics import YOLO
from notify_v1 import send_alert
from flask import Flask, Response

# === NEW: sensor libraries ===
from mpu6050 import mpu6050                # pip install mpu6050-raspberrypi
import sounddevice as sd                   # pip install sounddevice

# ------------------------------------------------------------------
# Argument parsing and initial setup (unchanged)
# ------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument('--model',     required=True, help='Path to YOLO model file')
parser.add_argument('--source',    required=True, help='… USB camera ("usb0"), Picamera ("picamera0"), etc.')
parser.add_argument('--thresh',    default=0.5,    help='Min confidence for drawing boxes')
parser.add_argument('--resolution',default=None,   help='Display/record resolution, e.g. "640x480"')
parser.add_argument('--record',    action='store_true', help='Save output as demo1.avi')
args = parser.parse_args()

model      = YOLO(args.model, task='detect')
labels     = model.names
min_thresh = float(args.thresh)
# ------------------------------------------------------------------
# NEW: sensor configuration
# ------------------------------------------------------------------
# MPU6050 motion sensor over I²C
mpu_address      = 0x68
motion_sensor    = mpu6050(mpu_address)
motion_threshold = 0.5   # in g’s
last_motion_alert = 0

# SPH0645LM4H via sounddevice (I2S)
sound_duration   = 0.5   # seconds to record per check
sound_fs         = 16000 # sampling rate
sound_threshold  = 0.02  # RMS amplitude threshold
last_sound_alert = 0

# Shared cooldown for YOLO alerts
last_yolo_alert = 0
yolo_cooldown   = 60    # seconds

# ------------------------------------------------------------------
# (rest of your source‐type, resolution, recorder, Flask setup)
# ------------------------------------------------------------------

app = Flask(__name__)

def generate_frames():
    global last_yolo_alert, last_motion_alert, last_sound_alert

    while True:
        start = time.perf_counter()
        # … (capture frame as before) …

        # 1) YOLO Inference + Box Drawing
        results    = model(frame, verbose=False)
        detections = results[0].boxes
        for box in detections:
            conf      = box.conf.item()
            cls_idx   = int(box.cls.item())
            name      = labels[cls_idx]
            xmin,ymin,xmax,ymax = box.xyxy.cpu().numpy().squeeze().astype(int)

            if conf > min_thresh:
                color = bbox_colors[cls_idx % len(bbox_colors)]
                cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), color, 2)
                cv2.putText(frame, f'{name}: {int(conf*100)}%', 
                            (xmin, ymin-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1)

                # NEW: only alert on person/car at ≥80%
                if name in ("person","car") and conf >= 0.8:
                    now = time.time()
                    if now - last_yolo_alert > yolo_cooldown:
                        send_alert("alert", f"YOLO: {name} detected ({int(conf*100)}%).")
                        last_yolo_alert = now

        # 2) Poll motion sensor
        accel = motion_sensor.get_accel_data()
        if (abs(accel['x'])>motion_threshold or
            abs(accel['y'])>motion_threshold or
            abs(accel['z'])>motion_threshold):
            now = time.time()
            if now - last_motion_alert > yolo_cooldown:
                send_alert("motion", "Motion near car detected!")
                last_motion_alert = now

        # 3) Poll sound sensor
        audio = sd.rec(int(sound_duration*sound_fs), samplerate=sound_fs, channels=1, blocking=True)
        rms   = np.sqrt(np.mean(audio**2))
        if rms > sound_threshold:
            now = time.time()
            if now - last_sound_alert > yolo_cooldown:
                send_alert("sound", "Suspicious sound detected!")
                last_sound_alert = now

        # … (FPS overlay, recording, MJPEG encoding, yield) …

        stop = time.perf_counter()
        # update your avg_frame_rate, etc.

@app.route('/video')
def video_feed():
    return Response(generate_frames(), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
