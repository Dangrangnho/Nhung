import cv2
import numpy as np
import os
import pandas as pd
from datetime import datetime
import time
import serial

# --- CẤU HÌNH ---
TRAINER_PATH = 'trainer/trainer.yml'
CASCADE_PATH = 'haarcascade_frontalface_default.xml'
ATTENDANCE_FILE = 'attendance.csv'
names = ['None', 'Hai Dang', 'Duc Anh', 'Quoc Dat']
FACE_SERIAL_CODES = {'Duc Anh': b'A', 'Hai Dang': b'B'}

CONFIDENCE_THRESHOLD = 75
VOTE_THRESHOLD = 40  # Giảm xuống một chút để nhạy hơn
COOLDOWN_SECONDS = 300
ARDUINO_PORT = 'COM5' 

# Biến trạng thái
vote_counter = {}
last_attendance_time = {}

# Khởi tạo OpenCV
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read(TRAINER_PATH)
faceCascade = cv2.CascadeClassifier(CASCADE_PATH)
font = cv2.FONT_HERSHEY_SIMPLEX

# Kết nối Arduino
try:
    ser = serial.Serial(ARDUINO_PORT, 9600, timeout=0.1)
    print(f"Connected to Arduino on {ARDUINO_PORT}")
except:
    print("Cannot connect to Arduino. Check COM port!")
    ser = None

def log_attendance(name):
    dt_string = datetime.now().strftime('%H:%M:%S - %d/%m/%Y')
    if not os.path.isfile(ATTENDANCE_FILE):
        pd.DataFrame(columns=['Ten', 'ThoiGian']).to_csv(ATTENDANCE_FILE, index=False)
    new_entry = pd.DataFrame([[name, dt_string]], columns=['Ten', 'ThoiGian'])
    new_entry.to_csv(ATTENDANCE_FILE, mode='a', header=False, index=False)
    last_attendance_time[name] = time.time()
    print(f"!!! LOGGED: {name} at {dt_string}")

cam = cv2.VideoCapture(0)

while True:
    ret, img = cam.read()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = faceCascade.detectMultiScale(gray, 1.2, 5, minSize=(100, 100))

    if len(faces) == 0:
        vote_counter = {}

    for (x, y, w, h) in faces:
        id_idx, confidence = recognizer.predict(gray[y:y+h, x:x+w])
        
        if confidence < CONFIDENCE_THRESHOLD:
            name = names[id_idx]
            vote_counter[name] = vote_counter.get(name, 0) + 1
            
            # Đủ số lần nhận diện khuôn mặt
            if vote_counter[name] >= VOTE_THRESHOLD:
                now = time.time()
                # Kiểm tra Cooldown
                if name not in last_attendance_time or (now - last_attendance_time[name] > COOLDOWN_SECONDS):
                    if ser and name in FACE_SERIAL_CODES:
                        # Gửi lệnh sang Arduino
                        ser.write(FACE_SERIAL_CODES[name])
                        print(f"Face OK: {name}. Waiting for RFID card...")
                        
                        # CHẾ ĐỘ CHỜ PHẢN HỒI (Handshake)
                        start_wait = time.time()
                        success = False
                        while time.time() - start_wait < 10: # Đợi tối đa 10s
                            if ser.in_waiting > 0:
                                line = ser.readline().decode('utf-8').strip()
                                if line == "OK":
                                    success = True
                                    break
                            time.sleep(0.05)
                        
                        if success:
                            log_attendance(name)
                            vote_counter = {} # Reset sau khi thành công
                        else:
                            print(f"Auth failed for {name} (RFID Timeout)")
                            vote_counter[name] = 0
                
                display_name = f"{name} - Authenticating..."
                color = (0, 255, 255)
            else:
                display_name = f"Scanning {name}... {vote_counter[name]}/{VOTE_THRESHOLD}"
                color = (255, 255, 0)
        else:
            display_name = "Unknown"
            color = (0, 0, 255)

        cv2.rectangle(img, (x, y), (x+w, y+h), color, 2)
        cv2.putText(img, display_name, (x+5, y-10), font, 0.7, color, 2)

    cv2.imshow('Attendance System', img)
    if cv2.waitKey(1) & 0xFF == 27: break

cam.release()
cv2.destroyAllWindows()
if ser: ser.close()