import cv2
import numpy as np
from PIL import Image
import os

# Đường dẫn đến thư mục cha chứa các folder dataset
# Theo hình ảnh bạn gửi, thư mục cha tên là 'DiemDanh',
# nhưng nếu file code python của bạn nằm CÙNG CẤP với 2 folder dataset kia
# thì bạn chỉ cần để root_path = '.' (thư mục hiện tại)
# Tuy nhiên, để an toàn và dễ hiểu, ta sẽ liệt kê danh sách các folder cần train:
dataset_folders = ['dataset_DucAnh', 'dataset_HaiDang', 'dataset_QuocDat']

recognizer = cv2.face.LBPHFaceRecognizer_create()
detector = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")


def getImagesAndLabels(folders):
    faceSamples = []
    ids = []

    # Lặp qua từng folder trong danh sách
    for folder_name in folders:
        # Kiểm tra folder có tồn tại không
        if not os.path.exists(folder_name):
            print(f"[CẢNH BÁO] Không tìm thấy thư mục: {folder_name}, bỏ qua.")
            continue

        print(f"[INFO] Đang quét thư mục: {folder_name}...")

        # Lấy danh sách đường dẫn tất cả file trong folder đó
        imagePaths = [os.path.join(folder_name, f) for f in os.listdir(folder_name) if
                      f.endswith('.jpg') or f.endswith('.png')]

        for imagePath in imagePaths:
            try:
                # Chuyển ảnh sang đen trắng (Grayscale)
                PIL_img = Image.open(imagePath).convert('L')
                img_numpy = np.array(PIL_img, 'uint8')

                # Lấy ID từ tên file (Cấu trúc: User.ID.Count.jpg)
                # Ví dụ: User.1.60.jpg -> Lấy số 1
                id = int(os.path.split(imagePath)[-1].split(".")[1])

                # Detect lại khuôn mặt để chắc chắn là lấy đúng phần mặt
                faces = detector.detectMultiScale(img_numpy)

                # Nếu tìm thấy mặt trong ảnh đã cắt (thường là sẽ thấy vì đã cắt chuẩn từ bước trước)
                for (x, y, w, h) in faces:
                    faceSamples.append(img_numpy[y:y + h, x:x + w])
                    ids.append(id)
            except Exception as e:
                print(f"Lỗi khi đọc file {imagePath}: {str(e)}")

    return faceSamples, ids


print("\n [INFO] Đang huấn luyện khuôn mặt cho các dataset:", dataset_folders)

faces, ids = getImagesAndLabels(dataset_folders)

if len(faces) == 0:
    print("\n [LỖI] Không tìm thấy khuôn mặt nào để train. Hãy kiểm tra lại đường dẫn.")
else:
    recognizer.train(faces, np.array(ids))

    # Lưu Models vào file trainer.yml
    if not os.path.exists('trainer'):
        os.makedirs('trainer')

    recognizer.write('trainer/trainer.yml')
    print(f"\n [INFO] THÀNH CÔNG! Đã huấn luyện {len(np.unique(ids))} người (IDs: {np.unique(ids)}).")
    print(" [INFO] File Models đã lưu tại trainer/trainer.yml")