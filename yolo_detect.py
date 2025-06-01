import os
import sys
import argparse
import glob
import time

import cv2
import numpy as np
from ultralytics import YOLO
from notify_v1 import send_alert
from flask import Flask, Response

# ------------------------------------------------------------------
# Argument parsing and initial setup
# ------------------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument('--model', help='Path to YOLO model file (example: "runs/detect/train/weights/best.pt")',
                    required=True)
parser.add_argument('--source', help='Image source, can be image file ("test.jpg"), image folder ("test_dir"), video file ("testvid.mp4"), index of USB camera ("usb0"), or index of Picamera ("picamera0")', 
                    required=True)
parser.add_argument('--thresh', help='Minimum confidence threshold for displaying detected objects (example: "0.4")',
                    default=0.5)
parser.add_argument('--resolution', help='Resolution in WxH to display inference results at (example: "640x480"), otherwise, match source resolution',
                    default=None)
parser.add_argument('--record', help='Record results from video or webcam and save it as "demo1.avi". Must specify --resolution argument to record.',
                    action='store_true')
args = parser.parse_args()

model_path = args.model
img_source = args.source
min_thresh = float(args.thresh)
user_res = args.resolution
record = args.record

if not os.path.exists(model_path):
    print('ERROR: Model path is invalid or model was not found. Make sure the model filename was entered correctly.')
    sys.exit(0)

model = YOLO(model_path, task='detect')
labels = model.names

# ------------------------------------------------------------------
# Determine image source type
# ------------------------------------------------------------------

img_ext_list = ['.jpg','.JPG','.jpeg','.JPEG','.png','.PNG','.bmp','.BMP']
vid_ext_list = ['.avi','.mov','.mp4','.mkv','.wmv']

if os.path.isdir(img_source):
    source_type = 'folder'
elif os.path.isfile(img_source):
    _, ext = os.path.splitext(img_source)
    if ext in img_ext_list:
        source_type = 'image'
    elif ext in vid_ext_list:
        source_type = 'video'
    else:
        print(f'File extension {ext} is not supported.')
        sys.exit(0)
elif 'usb' in img_source:
    source_type = 'usb'
    usb_idx = int(img_source[3:])
elif 'picamera' in img_source:
    source_type = 'picamera'
    picam_idx = int(img_source[8:])
else:
    print(f'Input {img_source} is invalid. Please try again.')
    sys.exit(0)

# ------------------------------------------------------------------
# Resolution setup
# ------------------------------------------------------------------

resize = False
if user_res:
    resize = True
    resW, resH = int(user_res.split('x')[0]), int(user_res.split('x')[1])

# ------------------------------------------------------------------
# Setup for recording (optional)
# ------------------------------------------------------------------

if record:
    if source_type not in ['video','usb']:
        print('Recording only works for video and camera sources. Please try again.')
        sys.exit(0)
    if not user_res:
        print('Please specify resolution to record video at.')
        sys.exit(0)
    
    record_name = 'demo1.avi'
    record_fps = 30
    recorder = cv2.VideoWriter(record_name, cv2.VideoWriter_fourcc(*'MJPG'), record_fps, (resW, resH))

# ------------------------------------------------------------------
# Initialize the video/image source
# ------------------------------------------------------------------

if source_type == 'image':
    imgs_list = [img_source]
elif source_type == 'folder':
    imgs_list = []
    filelist = glob.glob(img_source + '/*')
    for file in filelist:
        _, file_ext = os.path.splitext(file)
        if file_ext in img_ext_list:
            imgs_list.append(file)
elif source_type in ['video', 'usb']:
    cap_arg = img_source if source_type == 'video' else usb_idx
    cap = cv2.VideoCapture(cap_arg)
    if user_res:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resW)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resH)
elif source_type == 'picamera':
    from picamera2 import Picamera2
    cap = Picamera2()
    cap.configure(cap.create_video_configuration(main={"format": 'RGB888', "size": (resW, resH)}))
    cap.start()

# ------------------------------------------------------------------
# Other initializations
# ------------------------------------------------------------------

# Use the Tableau 10 color palette for bounding boxes
bbox_colors = [(164,120,87), (68,148,228), (93,97,209), (178,182,133), (88,159,106), 
               (96,202,231), (159,124,168), (169,162,241), (98,118,150), (172,176,184)]

avg_frame_rate = 0
frame_rate_buffer = []
fps_avg_len = 200
img_count = 0
last_alert_time = 0
cooldown_seconds = 60

# ------------------------------------------------------------------
# Flask app to serve the live stream as MJPEG
# ------------------------------------------------------------------

app = Flask(__name__)

def generate_frames():
    global img_count, last_alert_time, avg_frame_rate
    while True:
        t_start = time.perf_counter()

        # Capture frame from the source
        if source_type in ['image', 'folder']:
            if img_count >= len(imgs_list):
                break
            frame = cv2.imread(imgs_list[img_count])
            img_count += 1
        elif source_type == 'video':
            ret, frame = cap.read()
            if not ret:
                break
        elif source_type == 'usb':
            ret, frame = cap.read()
            if not ret or frame is None:
                break
        elif source_type == 'picamera':
            frame = cap.capture_array()
            if frame is None:
                break

        if resize:
            frame = cv2.resize(frame, (resW, resH))

        # Run YOLO inference on the frame
        results = model(frame, verbose=False)
        detections = results[0].boxes
        object_count = 0

        # Process detections to draw bounding boxes and labels
        for i in range(len(detections)):
            xyxy = detections[i].xyxy.cpu().numpy().squeeze().astype(int)
            # Check for edge-case when conversion returns a single number instead of array
            if xyxy.ndim == 0:
                continue
            xmin, ymin, xmax, ymax = xyxy
            classidx = int(detections[i].cls.item())
            classname = labels[classidx]
            conf = detections[i].conf.item()

            if conf > min_thresh:
                color = bbox_colors[classidx % 10]
                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2)
                label = f'{classname}: {int(conf*100)}%'
                labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                label_ymin = max(ymin, labelSize[1] + 10)
                cv2.rectangle(frame, (xmin, label_ymin - labelSize[1] - 10),
                              (xmin + labelSize[0], label_ymin + baseLine - 10), color, cv2.FILLED)
                cv2.putText(frame, label, (xmin, label_ymin - 7),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                object_count += 1

                # Alert for specific classes with a cooldown
                if classname in ["person", "car"]:
                    current_time = time.time()
                    if current_time - last_alert_time > cooldown_seconds:
                        print(f"🔔 Alert: Detected {classname} with confidence {conf:.2f}")
                        send_alert("alert", f"YOLO detected a {classname} near your car.")
                        last_alert_time = current_time

        # Draw additional info on the frame
        if source_type in ['video', 'usb', 'picamera']:
            cv2.putText(frame, f'FPS: {avg_frame_rate:0.2f}', (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, f'Number of objects: {object_count}', (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # Write frame to recorder if enabled
        if record:
            recorder.write(frame)

        # Calculate frame rate for display
        t_stop = time.perf_counter()
        frame_rate_calc = 1.0 / (t_stop - t_start)
        if len(frame_rate_buffer) >= fps_avg_len:
            frame_rate_buffer.pop(0)
        frame_rate_buffer.append(frame_rate_calc)
        avg_frame_rate = np.mean(frame_rate_buffer)

        # Encode the frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        frame_bytes = buffer.tobytes()

        # Yield the frame in multipart MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ------------------------------------------------------------------
# Run the Flask app
# ------------------------------------------------------------------

if __name__ == '__main__':
    # available at http://your-server-ip:5000/video
    app.run(host='0.0.0.0', port=5000)
