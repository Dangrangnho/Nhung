import cv2
import os

cam_id = 0
cap = cv2.VideoCapture(cam_id)
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

if not os.path.exists('dataset'):
    os.makedirs('dataset')

face_id = input('\n Nhập ID khuôn mặt: ')
print("\n [INFO] Camera đang chạy...")
print(" [NOTE] 100 khung hình đầu tiên sẽ KHÔNG được lưu (để bạn chuẩn bị).")

# Biến đếm số lần phát hiện khuôn mặt
current_frame = 0

# Cấu hình phạm vi lưu
start_save_at = 100  # Bắt đầu lưu từ ảnh thứ 60
stop_save_at = 1100  # Dừng khi đến ảnh thứ 1060

while True:
    ret, frame = cap.read()
    if not ret: break

    # Resize để chạy mượt
    frame = cv2.resize(frame, (640, 480))
    frame = cv2.flip(frame, 1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # Tăng biến đếm mỗi khi thấy mặt
        current_frame += 1

        # --- LOGIC MỚI ---
        if current_frame < start_save_at:
            # Giai đoạn CHUẨN BỊ (Chưa lưu)
            msg = f"Chuan bi: {current_frame}/{start_save_at}"
            color = (0, 255, 255)  # Màu vàng cảnh báo

        elif current_frame <= stop_save_at:
            # Giai đoạn LƯU ẢNH (Từ 60 -> 1060)
            cv2.imwrite(f"dataset/User.{face_id}.{current_frame}.jpg", gray[y:y + h, x:x + w])

            msg = f"Dang luu: {current_frame}/{stop_save_at}"
            color = (0, 255, 0)  # Màu xanh lá (đang hoạt động)

        else:
            # Đã vượt quá 1060 -> Thoát vòng lặp
            print(f"\n [INFO] Đã hoàn thành lưu đến ảnh {stop_save_at}.")
            cap.release()
            cv2.destroyAllWindows()
            exit()  # Thoát chương trình ngay lập tức

        # Hiển thị thông báo lên màn hình
        cv2.putText(frame, msg, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    cv2.imshow('Image', frame)

    k = cv2.waitKey(1) & 0xff
    if k == 27 or k == ord('q'):
        break

print("\n [INFO] Thoát chương trình.")
cap.release()
cv2.destroyAllWindows()