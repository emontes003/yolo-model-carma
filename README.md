# 🚗 CARMA Alert System

Python-based alert system using Firebase Cloud Messaging and Firestore. Sends push notifications when a person is detected near a vehicle.


This Python directory allows for the live stream to be integrated when running the command:
python yolo_detect.py --model my_model.pt --source usb0 --resolution 1280x720

Also must previously setup a virtual environment in Anaconda if on Windows:

conda create --name yolo-env1 python=3.12 -y
conda activate yolo-env1

pip install ultralytics
pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
