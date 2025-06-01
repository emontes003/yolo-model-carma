@echo off
call C:\Users\emont\anaconda3\Scripts\activate.bat yolo-env1
cd C:\Users\emont\Downloads\my_model
python yolo_detect.py --model my_model.pt --source usb0 --resolution 1280x720
pause
