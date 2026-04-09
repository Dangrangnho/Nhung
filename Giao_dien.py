import customtkinter as ctk
from tkinter import ttk
from PIL import Image
import cv2
import pandas as pd
import numpy as np
from datetime import datetime
import time
import serial
import threading
import os

# --- CẤU HÌNH ---
TRAINER_PATH = 'trainer/trainer.yml'
CASCADE_PATH = 'haarcascade_frontalface_default.xml'
ATTENDANCE_FILE = 'attendance.csv'
STUDENTS_FILE = 'students.csv'
DATASET_DIR = 'dataset'


CONFIDENCE_THRESHOLD = 75
VOTE_THRESHOLD = 10
COOLDOWN_SECONDS = 300
ARDUINO_PORT = 'COM5'

# --- UI THEME ---
COLOR_BG = "#0f172a"
COLOR_SIDEBAR = "#111827"
COLOR_CARD = "#1e293b"
COLOR_CARD_SOFT = "#0b1220"
COLOR_PRIMARY = "#3b82f6"
COLOR_PRIMARY_HOVER = "#2563eb"
COLOR_SUCCESS = "#22c55e"
COLOR_SUCCESS_HOVER = "#16a34a"
COLOR_DANGER = "#ef4444"
COLOR_DANGER_HOVER = "#dc2626"
COLOR_TEXT = "#e2e8f0"
COLOR_SUBTEXT = "#94a3b8"

# Cài đặt giao diện Dark Mode
ctk.set_appearance_mode("Dark")  # "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # "blue" (standard), "green", "dark-blue"


class AttendanceApp(ctk.CTk):
    """ Class quản lý Giao Diện Người Dùng (UI) """
    def __init__(self):
        super().__init__()

        self.title("Diem Danh FaceID + RFID by Dangrangnho")
        self.geometry("1150x700")
        self.minsize(950, 600)
        self.configure(fg_color=COLOR_BG)

        # Cấu hình grid tổng (1 hàng, 2 cột)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_main_view()

        # Khởi tạo và liên kết Logic với UI
        self.logic = AttendanceLogic(self)
        
        # Bắt sự kiện tắt cửa sổ để dừng camera an toàn
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_nav_button(self, parent, text, command=None, selected=False):
        return ctk.CTkButton(
            parent,
            text=text,
            corner_radius=12,
            height=44,
            border_width=1,
            fg_color=COLOR_PRIMARY if selected else "transparent",
            hover_color=COLOR_PRIMARY_HOVER if selected else "#1f2937",
            border_color=COLOR_PRIMARY if selected else "#334155",
            text_color=COLOR_TEXT,
            font=ctk.CTkFont(size=14, weight="bold" if selected else "normal"),
            command=command
        )

    def _set_active_nav(self, page):
        selected = {
            "home": self.btn_home,
            "students": self.btn_students,
            "history": self.btn_history
        }
        for key, btn in selected.items():
            is_active = (key == page)
            btn.configure(
                fg_color=COLOR_PRIMARY if is_active else "transparent",
                hover_color=COLOR_PRIMARY_HOVER if is_active else "#1f2937",
                border_color=COLOR_PRIMARY if is_active else "#334155",
                font=ctk.CTkFont(size=14, weight="bold" if is_active else "normal")
            )
        
    def _build_sidebar(self):
        # --- Tạo Sidebar bên trái ---
        self.sidebar_frame = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1) # Đẩy các nút start/stop xuống dưới

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="FaceID + RFID\nDashboard",
            text_color=COLOR_TEXT,
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 40))

        self.btn_home = self._create_nav_button(self.sidebar_frame, "🏠 Trang chủ", command=self.show_home, selected=True)
        self.btn_home.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.btn_students = self._create_nav_button(self.sidebar_frame, "🎓 Danh sách sinh viên", command=self.show_students)
        self.btn_students.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.btn_history = self._create_nav_button(self.sidebar_frame, "📜 Lịch sử điểm danh", command=self.show_all_history)
        self.btn_history.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        self.status_chip = ctk.CTkLabel(
            self.sidebar_frame,
            text="● Hệ thống: Đang dừng",
            text_color="#f8fafc",
            fg_color="#334155",
            corner_radius=10,
            padx=12,
            pady=6,
            font=ctk.CTkFont(size=12)
        )
        self.status_chip.grid(row=4, column=0, padx=20, pady=(10, 8), sticky="ew")
        
        self.btn_start = ctk.CTkButton(self.sidebar_frame, text="▶ Start System", fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER, 
                                       text_color="white", height=45, font=ctk.CTkFont(size=15, weight="bold"), command=self.start_system)
        self.btn_start.grid(row=7, column=0, padx=20, pady=(10, 5), sticky="ew")
        
        self.btn_stop = ctk.CTkButton(self.sidebar_frame, text="⏹ Stop System", fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER, 
                                      text_color="white", height=45, font=ctk.CTkFont(size=15, weight="bold"), command=self.stop_system, state="disabled")
        self.btn_stop.grid(row=8, column=0, padx=20, pady=(5, 30), sticky="ew")

    def _build_main_view(self):
        # --- Tạo Home View (Camera + Info + Table 5 gần nhất) ---
        self.home_view_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.home_view_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.home_view_frame.grid_rowconfigure(0, weight=0) # Header block
        self.home_view_frame.grid_rowconfigure(1, weight=3) # Camera and Info block
        self.home_view_frame.grid_rowconfigure(2, weight=2) # Table block
        self.home_view_frame.grid_columnconfigure(0, weight=3) # Camera rộng hơn
        self.home_view_frame.grid_columnconfigure(1, weight=1) # Info hẹp hơn

        self.dashboard_header = ctk.CTkFrame(self.home_view_frame, fg_color="transparent")
        self.dashboard_header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 4))
        self.dashboard_title = ctk.CTkLabel(
            self.dashboard_header,
            text="Realtime Attendance",
            text_color=COLOR_TEXT,
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.dashboard_title.pack(side="left")
        self.dashboard_subtitle = ctk.CTkLabel(
            self.dashboard_header,
            text="Camera + FaceID + RFID",
            text_color=COLOR_SUBTEXT,
            font=ctk.CTkFont(size=13)
        )
        self.dashboard_subtitle.pack(side="right")

        # --- Camera Frame ---
        self.camera_frame = ctk.CTkFrame(self.home_view_frame, corner_radius=16, fg_color=COLOR_CARD)
        self.camera_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.camera_frame.pack_propagate(False) # Cố định layout để không bị co giãn khi chưa load hình

        self.camera_label = ctk.CTkLabel(self.camera_frame, text="[ Camera Feed ]", font=ctk.CTkFont(size=18), text_color=COLOR_SUBTEXT)
        self.camera_label.pack(expand=True, fill="both", padx=10, pady=10)

        # --- Info Panel ---
        self.info_frame = ctk.CTkFrame(self.home_view_frame, corner_radius=16, fg_color=COLOR_CARD)
        self.info_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

        self.info_title = ctk.CTkLabel(self.info_frame, text="THÔNG TIN QUÉT", text_color=COLOR_TEXT, font=ctk.CTkFont(size=18, weight="bold"))
        self.info_title.pack(pady=(20, 15))

        self.info_content = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        self.info_content.pack(fill="both", expand=True, padx=20)

        self.lbl_name = ctk.CTkLabel(self.info_content, text="👤 Họ tên: --", text_color=COLOR_TEXT, font=ctk.CTkFont(size=16))
        self.lbl_name.pack(anchor="w", pady=12)
        
        self.lbl_id = ctk.CTkLabel(self.info_content, text="💳 MSSV: --", text_color=COLOR_TEXT, font=ctk.CTkFont(size=16))
        self.lbl_id.pack(anchor="w", pady=12)

        self.lbl_time = ctk.CTkLabel(self.info_content, text="🕒 Thời gian: --", text_color=COLOR_TEXT, font=ctk.CTkFont(size=16))
        self.lbl_time.pack(anchor="w", pady=12)

        self.lbl_rfid = ctk.CTkLabel(self.info_content, text="📡 RFID: Chưa có", text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=16))
        self.lbl_rfid.pack(anchor="w", pady=12)

        # --- Data Table ---
        self.table_frame = ctk.CTkFrame(self.home_view_frame, corner_radius=16, fg_color=COLOR_CARD)
        self.table_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        self.table_title = ctk.CTkLabel(self.table_frame, text="5 NGƯỜI ĐIỂM DANH GẦN NHẤT", text_color=COLOR_TEXT, font=ctk.CTkFont(size=16, weight="bold"))
        self.table_title.pack(anchor="w", padx=20, pady=(15, 5))

        # Setup giao diện Bảng (Treeview của tkinter được style lại cho hợp với Dark Mode)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=COLOR_CARD_SOFT,
                        foreground=COLOR_TEXT,
                        rowheight=34,
                        fieldbackground=COLOR_CARD_SOFT,
                        bordercolor=COLOR_CARD_SOFT,
                        borderwidth=0,
                        font=('Segoe UI', 11))
                        
        style.map('Treeview', background=[('selected', COLOR_PRIMARY)])
        style.configure("Treeview.Heading",
                        background="#111827",
                        foreground="#f8fafc",
                        relief="flat",
                        rowheight=38,
                        font=('Segoe UI Semibold', 11))
        style.map("Treeview.Heading", background=[('active', "#1f2937")])

        self.tree = ttk.Treeview(self.table_frame, columns=("STT", "Họ tên", "MSSV", "Thời gian"), show='headings', height=5)
        self.tree.heading("STT", text="STT")
        self.tree.heading("Họ tên", text="Họ Tên")
        self.tree.heading("MSSV", text="MSSV")
        self.tree.heading("Thời gian", text="Thời Gian")
        
        self.tree.column("STT", width=50, anchor="center")
        self.tree.column("Họ tên", width=250, anchor="w")
        self.tree.column("MSSV", width=150, anchor="center")
        self.tree.column("Thời gian", width=200, anchor="center")
        self.tree.pack(expand=True, fill="both", padx=20, pady=(0, 20))
        
        # --- Tạo History View (Bảng lịch sử đầy đủ) ---
        self.history_view_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.history_view_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.history_view_frame.grid_rowconfigure(0, weight=0)  # Header
        self.history_view_frame.grid_rowconfigure(1, weight=1)  # Table
        self.history_view_frame.grid_rowconfigure(2, weight=0)  # Footer
        self.history_view_frame.grid_columnconfigure(0, weight=1)
        
        # Header cho History View
        self.history_header = ctk.CTkFrame(self.history_view_frame, fg_color="transparent")
        self.history_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        
        self.history_title = ctk.CTkLabel(self.history_header, text="LỊCH SỬ ĐIỂM DANH ĐẦY ĐỦ", font=ctk.CTkFont(size=18, weight="bold"))
        self.history_title.pack(anchor="w")
        
        # Table cho History View
        self.history_table_frame = ctk.CTkFrame(self.history_view_frame, corner_radius=16, fg_color=COLOR_CARD)
        self.history_table_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        
        self.history_tree = ttk.Treeview(self.history_table_frame, columns=("STT", "Họ tên", "MSSV", "Thời gian"), show='headings')
        self.history_tree.heading("STT", text="STT")
        self.history_tree.heading("Họ tên", text="Họ Tên")
        self.history_tree.heading("MSSV", text="MSSV")
        self.history_tree.heading("Thời gian", text="Thời Gian")
        
        self.history_tree.column("STT", width=50, anchor="center")
        self.history_tree.column("Họ tên", width=250, anchor="w")
        self.history_tree.column("MSSV", width=150, anchor="center")
        self.history_tree.column("Thời gian", width=200, anchor="center")
        self.history_tree.pack(expand=True, fill="both")
        
        # Footer cho History View (Nút quay lại)
        self.history_footer = ctk.CTkFrame(self.history_view_frame, fg_color="transparent")
        self.history_footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))
        
        self.btn_back_home = ctk.CTkButton(self.history_footer, text="← Quay lại Trang Chủ", font=ctk.CTkFont(size=14),
                                          fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, command=self.show_home)
        self.btn_back_home.pack(anchor="w")
        
        # Ban đầu ẩn history view
        self.history_view_frame.grid_remove()
        
        # --- Tạo Students View (Danh sách sinh viên) ---
        self.students_view_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.students_view_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.students_view_frame.grid_rowconfigure(0, weight=0)  # Header
        self.students_view_frame.grid_rowconfigure(1, weight=1)  # Table
        self.students_view_frame.grid_rowconfigure(2, weight=0)  # Buttons
        self.students_view_frame.grid_rowconfigure(3, weight=0)  # Footer
        self.students_view_frame.grid_columnconfigure(0, weight=1)
        
        # Header cho Students View
        self.students_header = ctk.CTkFrame(self.students_view_frame, fg_color="transparent")
        self.students_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        
        self.students_title = ctk.CTkLabel(self.students_header, text="DANH SÁCH SINH VIÊN", font=ctk.CTkFont(size=18, weight="bold"))
        self.students_title.pack(anchor="w")
        
        # Table cho Students View
        self.students_table_frame = ctk.CTkFrame(self.students_view_frame, corner_radius=16, fg_color=COLOR_CARD)
        self.students_table_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        
        self.students_tree = ttk.Treeview(self.students_table_frame, columns=("STT", "Tên", "MSSV", "RFID_UID"), show='headings', height=15)
        self.students_tree.heading("STT", text="STT")
        self.students_tree.heading("Tên", text="Tên Sinh Viên")
        self.students_tree.heading("MSSV", text="Mã Sinh Viên")
        self.students_tree.heading("RFID_UID", text="RFID UID")
        
        self.students_tree.column("STT", width=50, anchor="center")
        self.students_tree.column("Tên", width=250, anchor="w")
        self.students_tree.column("MSSV", width=150, anchor="center")
        self.students_tree.column("RFID_UID", width=150, anchor="center")
        self.students_tree.pack(expand=True, fill="both")
        
        # Action Buttons
        self.students_button_frame = ctk.CTkFrame(self.students_view_frame, fg_color="transparent")
        self.students_button_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 10))
        
        self.btn_add_student = ctk.CTkButton(self.students_button_frame, text="➕ Thêm", font=ctk.CTkFont(size=13, weight="bold"),
                                            fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER, command=self.add_student_dialog)
        self.btn_add_student.pack(side="left", padx=5)
        
        self.btn_edit_student = ctk.CTkButton(self.students_button_frame, text="✏️ Sửa", font=ctk.CTkFont(size=13, weight="bold"),
                                             fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, command=self.edit_student_dialog)
        self.btn_edit_student.pack(side="left", padx=5)
        
        self.btn_delete_student = ctk.CTkButton(self.students_button_frame, text="🗑️ Xóa", font=ctk.CTkFont(size=13, weight="bold"),
                                               fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER, command=self.delete_student_dialog)
        self.btn_delete_student.pack(side="left", padx=5)
        
        # Footer cho Students View (Nút quay lại)
        self.students_footer = ctk.CTkFrame(self.students_view_frame, fg_color="transparent")
        self.students_footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        self.btn_back_home_students = ctk.CTkButton(self.students_footer, text="← Quay lại Trang Chủ", font=ctk.CTkFont(size=14),
                                                   fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, command=self.show_home)
        self.btn_back_home_students.pack(anchor="w")
        
        # Ban đầu ẩn students view
        self.students_view_frame.grid_remove()

    # --- Các hàm thao tác UI (Để cho Logic Class gọi sang) ---
    def update_camera_image(self, ctk_img):
        self.camera_label.configure(image=ctk_img, text="")
        self.camera_label.image = ctk_img

    def update_student_info(self, name, student_id, scan_time, rfid_status):
        self.lbl_name.configure(text=f"👤 Họ tên: {name}")
        self.lbl_id.configure(text=f"💳 MSSV: {student_id}")
        self.lbl_time.configure(text=f"🕒 Thời gian: {scan_time}")
        
        color = "#2ecc71" if rfid_status.lower() in ["success", "ok", "thành công"] else ("#f1c40f" if "đang" in rfid_status.lower() else "#e74c3c")
        self.lbl_rfid.configure(text=f"📡 RFID: {rfid_status}", text_color=color)

    def update_table(self, records, show_all=False):
        """Cập nhật bảng hiển thị với dữ liệu
        Args:
            records: Danh sách bản ghi
            show_all: Nếu True, hiển thị toàn bộ; nếu False, chỉ hiển thị 5 dòng mới nhất
        """
        for row in self.tree.get_children():
            self.tree.delete(row)
        # Hiển thị dữ liệu (5 dòng nếu show_all=False, toàn bộ nếu show_all=True)
        display_records = records if show_all else records[:5]
        for idx, record in enumerate(display_records):
            stt = idx + 1
            if len(record) == 3: 
                self.tree.insert("", "end", values=(stt, *record))
            
    # --- Điều hướng Tương tác ---
    def start_system(self):
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_chip.configure(text="● Hệ thống: Đang chạy", fg_color="#14532d")
        self.logic.start_recognition()

    def stop_system(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_chip.configure(text="● Hệ thống: Đang dừng", fg_color="#334155")
        self.logic.stop_recognition()
        self.camera_label.configure(image="", text="[ Camera Stopped ]")

    def show_all_history(self):
        """Hiển thị giao diện lịch sử toàn bộ — đọc thẳng từ attendance.csv"""
        self._set_active_nav("history")
        # Ẩn tất cả view khác trước
        self.home_view_frame.grid_remove()
        self.students_view_frame.grid_remove()

        # Xóa dữ liệu cũ trong history_tree
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        if os.path.isfile(ATTENDANCE_FILE):
            try:
                df = pd.read_csv(ATTENDANCE_FILE, engine='python', on_bad_lines='skip')
                # Đảm bảo có đúng cột cần thiết
                if 'Ten' in df.columns and 'ThoiGian' in df.columns:
                    # Đảo ngược: mới nhất lên trên cùng
                    all_records = df.iloc[::-1].reset_index(drop=True)
                    for idx, (_, row) in enumerate(all_records.iterrows(), 1):
                        mssv = row.get('MSSV', 'N/A') if 'MSSV' in row else 'N/A'
                        self.history_tree.insert("", "end", values=(idx, row['Ten'], mssv, row['ThoiGian']))
                else:
                    print("[Warning] File attendance.csv thiếu cột 'Ten' hoặc 'ThoiGian'.")
            except Exception as e:
                print(f"[Error] Không đọc được lịch sử: {str(e)}")
        else:
            print("[Info] Chưa có file attendance.csv.")

        # Hiện history view
        self.history_view_frame.grid()
    
    def show_home(self):
        """Quay lại trang chủ"""
        self._set_active_nav("home")
        self.logic.refresh_recent_attendance()
        self.history_view_frame.grid_remove()
        self.students_view_frame.grid_remove()
        self.home_view_frame.grid()

    def show_students(self):
        """Hiển thị giao diện danh sách sinh viên"""
        self._set_active_nav("students")
        self.load_students_list()
        self.home_view_frame.grid_remove()
        self.history_view_frame.grid_remove()
        self.students_view_frame.grid()
    
    def load_students_list(self):
        """Load danh sách sinh viên từ CSV"""
        for item in self.students_tree.get_children():
            self.students_tree.delete(item)
        
        if os.path.isfile(STUDENTS_FILE):
            try:
                df = pd.read_csv(STUDENTS_FILE)
                if 'Ten' in df.columns and 'MSSV' in df.columns:
                    self.logic.load_student_map()
                    for idx, (_, row) in enumerate(df.iterrows(), 1):
                        rfid_uid = row['RFID_UID'] if 'RFID_UID' in row and pd.notna(row['RFID_UID']) else ''
                        self.students_tree.insert("", "end", values=(idx, row['Ten'], row['MSSV'], rfid_uid))
            except Exception as e:
                print(f"Error loading students: {str(e)}")
    
    def add_student_dialog(self):
        """Mở dialog thêm sinh viên mới"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Thêm Sinh Viên")
        dialog.geometry("400x440")
        
        label_name = ctk.CTkLabel(dialog, text="Tên sinh viên:", font=ctk.CTkFont(size=12))
        label_name.pack(pady=(20, 5), padx=20, anchor="w")
        
        entry_name = ctk.CTkEntry(dialog, font=ctk.CTkFont(size=12))
        entry_name.pack(pady=(5, 10), padx=20, fill="x")
        
        label_mssv = ctk.CTkLabel(dialog, text="Mã sinh viên:", font=ctk.CTkFont(size=12))
        label_mssv.pack(pady=(5, 5), padx=20, anchor="w")
        
        entry_mssv = ctk.CTkEntry(dialog, font=ctk.CTkFont(size=12))
        entry_mssv.pack(pady=(5, 10), padx=20, fill="x")
        
        label_rfid = ctk.CTkLabel(dialog, text="RFID UID (hex, ví dụ: 86BE8005):", font=ctk.CTkFont(size=12))
        label_rfid.pack(pady=(5, 5), padx=20, anchor="w")
        
        entry_rfid = ctk.CTkEntry(dialog, font=ctk.CTkFont(size=12), placeholder_text="Để trống nếu chưa có thẻ")
        entry_rfid.pack(pady=(5, 10), padx=20, fill="x")

        capture_face_var = ctk.BooleanVar(value=True)
        chk_capture_face = ctk.CTkCheckBox(
            dialog,
            text="Thu thập khuôn mặt ngay sau khi thêm",
            variable=capture_face_var,
            font=ctk.CTkFont(size=12)
        )
        chk_capture_face.pack(pady=(5, 5), padx=20, anchor="w")

        note_label = ctk.CTkLabel(
            dialog,
            text="Lưu ý: camera sẽ mở để chụp ảnh và train lại model.",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        note_label.pack(pady=(0, 10), padx=20, anchor="w")
        
        def save_student():
            name = entry_name.get().strip()
            mssv = entry_mssv.get().strip()
            rfid_uid = entry_rfid.get().strip().upper()
            
            if not name or not mssv:
                print("Vui lòng điền đầy đủ thông tin")
                return
            
            # Thêm vào CSV
            if os.path.isfile(STUDENTS_FILE):
                df = pd.read_csv(STUDENTS_FILE)
            else:
                df = pd.DataFrame(columns=['Ten', 'MSSV', 'RFID_UID', 'FaceID'])

            if 'FaceID' not in df.columns:
                df['FaceID'] = None

            existing_ids = pd.to_numeric(df['FaceID'], errors='coerce').dropna().astype(int)
            next_face_id = int(existing_ids.max()) + 1 if not existing_ids.empty else 1
            
            new_entry = pd.DataFrame(
                [[name, mssv, rfid_uid, next_face_id]],
                columns=['Ten', 'MSSV', 'RFID_UID', 'FaceID']
            )
            df = pd.concat([df, new_entry], ignore_index=True)
            df.to_csv(STUDENTS_FILE, index=False)

            self.logic.load_student_map()

            if capture_face_var.get():
                print(f"[INFO] Bắt đầu thu thập khuôn mặt cho {name} (FaceID: {next_face_id})...")
                ok_collect = self.logic.collect_face_data(next_face_id)
                if ok_collect:
                    print("[INFO] Đang train lại mô hình...")
                    ok_train = self.logic.train_recognizer_from_dataset()
                    if ok_train:
                        self.logic.reload_recognizer_model()
                        print("[INFO] Hoàn tất thêm sinh viên + cập nhật khuôn mặt.")
                    else:
                        print("[Warning] Đã thêm sinh viên nhưng train model thất bại.")
                else:
                    print("[Warning] Đã thêm sinh viên nhưng thu thập khuôn mặt chưa hoàn tất.")
            
            self.load_students_list()
            dialog.destroy()
        
        def cancel_dialog():
            dialog.destroy()
        
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10, padx=20, fill="x")
        
        btn_save = ctk.CTkButton(button_frame, text="✓ OK", command=save_student, font=ctk.CTkFont(size=12), fg_color="#2ecc71")
        btn_save.pack(side="left", padx=5, fill="x", expand=True)
        
        btn_cancel = ctk.CTkButton(button_frame, text="✕ Hủy", command=cancel_dialog, font=ctk.CTkFont(size=12), fg_color="#e74c3c")
        btn_cancel.pack(side="left", padx=5, fill="x", expand=True)
    
    def edit_student_dialog(self):
        """Mở dialog sửa sinh viên"""
        selection = self.students_tree.selection()
        if not selection:
            print("Vui lòng chọn sinh viên cần sửa")
            return
        
        item = selection[0]
        values = self.students_tree.item(item)['values']
        row_index = values[0] - 1
        current_name = values[1]
        current_mssv = values[2]
        current_rfid = str(values[3]) if len(values) > 3 and values[3] else ''
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Sửa Sinh Viên")
        dialog.geometry("400x370")
        
        label_name = ctk.CTkLabel(dialog, text="Tên sinh viên:", font=ctk.CTkFont(size=12))
        label_name.pack(pady=(20, 5), padx=20, anchor="w")
        
        entry_name = ctk.CTkEntry(dialog, font=ctk.CTkFont(size=12))
        entry_name.insert(0, current_name)
        entry_name.pack(pady=(5, 10), padx=20, fill="x")
        
        label_mssv = ctk.CTkLabel(dialog, text="Mã sinh viên:", font=ctk.CTkFont(size=12))
        label_mssv.pack(pady=(5, 5), padx=20, anchor="w")
        
        entry_mssv = ctk.CTkEntry(dialog, font=ctk.CTkFont(size=12))
        entry_mssv.insert(0, current_mssv)
        entry_mssv.pack(pady=(5, 10), padx=20, fill="x")
        
        label_rfid = ctk.CTkLabel(dialog, text="RFID UID (hex, ví dụ: 86BE8005):", font=ctk.CTkFont(size=12))
        label_rfid.pack(pady=(5, 5), padx=20, anchor="w")
        
        entry_rfid = ctk.CTkEntry(dialog, font=ctk.CTkFont(size=12), placeholder_text="Để trống nếu chưa có thẻ")
        if current_rfid:
            entry_rfid.insert(0, current_rfid)
        entry_rfid.pack(pady=(5, 10), padx=20, fill="x")
        
        def update_student():
            name = entry_name.get().strip()
            mssv = entry_mssv.get().strip()
            rfid_uid = entry_rfid.get().strip().upper()
            
            if not name or not mssv:
                print("Vui lòng điền đầy đủ thông tin")
                return
            
            df = pd.read_csv(STUDENTS_FILE)
            if 0 <= row_index < len(df):
                df.at[row_index, 'Ten'] = name
                df.at[row_index, 'MSSV'] = mssv
                df.at[row_index, 'RFID_UID'] = rfid_uid
                df.to_csv(STUDENTS_FILE, index=False)
                self.load_students_list()
            else:
                print("Lỗi: không tìm thấy dòng sinh viên để sửa")
            dialog.destroy()
        
        def cancel_dialog():
            dialog.destroy()
        
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10, padx=20, fill="x")
        
        btn_save = ctk.CTkButton(button_frame, text="✓ OK", command=update_student, font=ctk.CTkFont(size=12), fg_color="#2ecc71")
        btn_save.pack(side="left", padx=5, fill="x", expand=True)
        
        btn_cancel = ctk.CTkButton(button_frame, text="✕ Hủy", command=cancel_dialog, font=ctk.CTkFont(size=12), fg_color="#e74c3c")
        btn_cancel.pack(side="left", padx=5, fill="x", expand=True)
    
    def delete_student_dialog(self):
        """Xóa sinh viên được chọn"""
        selection = self.students_tree.selection()
        if not selection:
            print("Vui lòng chọn sinh viên cần xóa")
            return
        
        item = selection[0]
        values = self.students_tree.item(item)['values']
        row_index = values[0] - 1
        name = values[1]
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Xác Nhận Xóa")
        dialog.geometry("350x120")
        
        label_confirm = ctk.CTkLabel(dialog, text=f"Bạn chắc chắn muốn xóa sinh viên '{name}' không?", font=ctk.CTkFont(size=12))
        label_confirm.pack(pady=20, padx=20)
        
        def confirm_delete():
            df = pd.read_csv(STUDENTS_FILE)
            if 0 <= row_index < len(df):
                df = df.drop(df.index[row_index]).reset_index(drop=True)
                df.to_csv(STUDENTS_FILE, index=False)
                self.load_students_list()
                print(f"Đã xóa sinh viên: {name}")
            else:
                print("Lỗi: không tìm thấy dòng sinh viên để xóa")
            dialog.destroy()
        
        def cancel_delete():
            dialog.destroy()
        
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10, padx=20, fill="x")
        
        btn_ok = ctk.CTkButton(button_frame, text="✓ OK", command=confirm_delete, font=ctk.CTkFont(size=12), fg_color="#e74c3c")
        btn_ok.pack(side="left", padx=5, fill="x", expand=True)
        
        btn_cancel = ctk.CTkButton(button_frame, text="✕ Hủy", command=cancel_delete, font=ctk.CTkFont(size=12), fg_color="#95a5a6")
        btn_cancel.pack(side="left", padx=5, fill="x", expand=True)

    def on_closing(self):
        self.logic.stop_recognition()
        self.destroy()


class AttendanceLogic:
    """ Class Tách Biệt Chứa Toàn Bộ Logic (Camera, OpenCV, Arduino Serial, File Logging) """
    def __init__(self, ui_instance):
        self.ui = ui_instance
        self.running = False
        self.cam = None
        self.thread = None
        
        # Biến trạng thái
        self.vote_counter = {}
        self.last_attendance_time = {}
        self.recent_records = []
        self.student_mssv_map = {}
        self.student_rfid_map = {}
        self.faceid_name_map = {}
        
        self.load_student_map()
        self.load_initial_data()
        
        # Khởi tạo mô hình OpenCV
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        try:
            self.recognizer.read(TRAINER_PATH)
            self.faceCascade = cv2.CascadeClassifier(CASCADE_PATH)
        except Exception as e:
            print("[Warning] Không tìm thấy file mô hình. Bỏ qua nhận diện khuôn mặt.")
            
        self.font = cv2.FONT_HERSHEY_SIMPLEX

        # Kết nối Arduino
        try:
            self.ser = serial.Serial(ARDUINO_PORT, 9600, timeout=0.1)
            print(f"Connected to Arduino on {ARDUINO_PORT}")
        except:
            print(f"Cannot connect to Arduino on {ARDUINO_PORT}.")
            self.ser = None

    def load_initial_data(self):
        """Load toàn bộ lịch sử điểm danh từ CSV khi app khởi động"""
        self.refresh_recent_attendance()

    def refresh_recent_attendance(self):
        """Luôn đọc lại 5 bản ghi điểm danh gần nhất từ attendance.csv (không dùng cache)"""
        self.recent_records = []
        if os.path.isfile(ATTENDANCE_FILE):
            try:
                df = pd.read_csv(ATTENDANCE_FILE, engine='python', on_bad_lines='skip')
                if 'Ten' in df.columns and 'ThoiGian' in df.columns:
                    # Lấy 5 dòng cuối cùng (mới nhất), đảo chiều
                    latest = df.tail(5).iloc[::-1].reset_index(drop=True)
                    for _, row in latest.iterrows():
                        mssv = row['MSSV'] if 'MSSV' in row and pd.notna(row['MSSV']) else 'N/A'
                        self.recent_records.append((row['Ten'], mssv, row['ThoiGian']))
                else:
                    print("[Warning] File attendance.csv thiếu cột 'Ten' hoặc 'ThoiGian'.")
            except Exception as e:
                print(f"[Error] Không đọc được dữ liệu gần nhất: {str(e)}")
        # Luôn gọi update dù danh sách rỗng
        self.ui.after(0, self.ui.update_table, self.recent_records)

    def load_student_map(self):
        """Load bản đồ tên -> MSSV và tên -> RFID_UID từ file students.csv"""
        self.student_mssv_map = {}
        self.student_rfid_map = {}
        self.faceid_name_map = {}
        if os.path.isfile(STUDENTS_FILE):
            try:
                df = pd.read_csv(STUDENTS_FILE)
                if 'Ten' in df.columns and 'MSSV' in df.columns:
                    self.student_mssv_map = dict(zip(df['Ten'].astype(str), df['MSSV'].astype(str)))
                if 'Ten' in df.columns and 'RFID_UID' in df.columns:
                    for _, row in df.iterrows():
                        uid = str(row['RFID_UID']).strip() if pd.notna(row['RFID_UID']) else ''
                        if uid:
                            self.student_rfid_map[str(row['Ten'])] = uid.upper()
                if 'Ten' in df.columns:
                    if 'FaceID' in df.columns:
                        for _, row in df.iterrows():
                            if pd.notna(row.get('FaceID')):
                                try:
                                    face_id = int(row['FaceID'])
                                    self.faceid_name_map[face_id] = str(row['Ten'])
                                except Exception:
                                    continue
                    else:
                        # Tương thích dữ liệu cũ khi chưa có cột FaceID.
                        for idx, (_, row) in enumerate(df.iterrows(), start=1):
                            self.faceid_name_map[idx] = str(row['Ten'])
            except Exception as e:
                print(f"Error loading student map: {str(e)}")

    def collect_face_data(self, face_id, warmup_frames=30, target_samples=100):
        """Thu thập ảnh khuôn mặt cho 1 sinh viên vào thư mục dataset."""
        if not os.path.exists(DATASET_DIR):
            os.makedirs(DATASET_DIR)

        face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
        if face_cascade.empty():
            print("[Error] Không load được haarcascade.")
            return False

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[Error] Không mở được camera để thu thập khuôn mặt.")
            return False

        saved_count = 0
        frame_count = 0
        print("[INFO] Nhấn Q để hủy thu thập khuôn mặt.")

        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame = cv2.resize(frame, (640, 480))
            frame = cv2.flip(frame, 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)

            frame_count += 1
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                if frame_count > warmup_frames and saved_count < target_samples:
                    saved_count += 1
                    filename = os.path.join(DATASET_DIR, f"User.{face_id}.{saved_count}.jpg")
                    cv2.imwrite(filename, gray[y:y + h, x:x + w])

            cv2.putText(
                frame,
                f"Saved: {saved_count}/{target_samples}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )
            cv2.imshow("Collect Face Data", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            if saved_count >= target_samples:
                break

        cap.release()
        cv2.destroyAllWindows()
        return saved_count >= target_samples

    def train_recognizer_from_dataset(self):
        """Train LBPH từ thư mục dataset/User.<FaceID>.<index>.jpg"""
        if not os.path.exists(DATASET_DIR):
            print("[Error] Chưa có thư mục dataset.")
            return False

        detector = cv2.CascadeClassifier(CASCADE_PATH)
        if detector.empty():
            print("[Error] Không load được haarcascade để train.")
            return False

        image_paths = [
            os.path.join(DATASET_DIR, f)
            for f in os.listdir(DATASET_DIR)
            if f.lower().endswith((".jpg", ".png"))
        ]

        face_samples = []
        ids = []

        for image_path in image_paths:
            file_name = os.path.basename(image_path)
            parts = file_name.split(".")
            if len(parts) < 4 or parts[0] != "User":
                continue
            try:
                face_id = int(parts[1])
            except Exception:
                continue

            try:
                pil_img = Image.open(image_path).convert('L')
                img_numpy = np.array(pil_img, 'uint8')
                faces = detector.detectMultiScale(img_numpy)
                if len(faces) == 0:
                    face_samples.append(img_numpy)
                    ids.append(face_id)
                else:
                    for (x, y, w, h) in faces:
                        face_samples.append(img_numpy[y:y + h, x:x + w])
                        ids.append(face_id)
            except Exception:
                continue

        if not face_samples:
            print("[Error] Không có dữ liệu khuôn mặt hợp lệ để train.")
            return False

        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(face_samples, np.array(ids))

        if not os.path.exists('trainer'):
            os.makedirs('trainer')
        recognizer.write(TRAINER_PATH)
        print(f"[INFO] Train thành công {len(set(ids))} người.")
        return True

    def reload_recognizer_model(self):
        """Nạp lại model nhận diện sau khi train."""
        try:
            self.recognizer.read(TRAINER_PATH)
            self.load_student_map()
        except Exception as e:
            print(f"[Warning] Không nạp lại được model mới: {str(e)}")

    def start_recognition(self):
        if not self.running:
            self.running = True
            self.cam = cv2.VideoCapture(0)
            self.thread = threading.Thread(target=self.recognition_loop, daemon=True)
            self.thread.start()

    def stop_recognition(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cam:
            self.cam.release()
            self.cam = None

    def get_mssv_of(self, name):
        return self.student_mssv_map.get(name, "Unknown")

    def get_rfid_uid_of(self, name):
        """Lấy RFID UID của sinh viên từ bản đồ đã load"""
        return self.student_rfid_map.get(name, "")

    def log_attendance(self, name, success_time=None):
        if success_time is None:
            success_time = datetime.now()
        dt_string = success_time.strftime('%H:%M:%S')
        date_string = success_time.strftime('%d/%m/%Y')
        full_time = f"{dt_string} - {date_string}"
        mssv = self.get_mssv_of(name)
        
        # Ghi Log
        if not os.path.isfile(ATTENDANCE_FILE):
            pd.DataFrame(columns=['Ten', 'MSSV', 'ThoiGian']).to_csv(ATTENDANCE_FILE, index=False)
        new_entry = pd.DataFrame([[name, mssv, full_time]], columns=['Ten', 'MSSV', 'ThoiGian'])
        new_entry.to_csv(ATTENDANCE_FILE, mode='a', header=False, index=False)
        
        self.last_attendance_time[name] = time.time()
        # Sau khi ghi xong, đọc lại từ CSV để bảng luôn đúng
        self.refresh_recent_attendance()

    def recognition_loop(self):
        """ Vòng lặp camera chạy trong một luồng (thread) riêng """
        while self.running:
            if not self.cam or not self.cam.isOpened():
                break
                
            ret, img = self.cam.read()
            if not ret:
                time.sleep(0.01)
                continue

            try:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # Face detection routine
                if hasattr(self, 'faceCascade') and not self.faceCascade.empty():
                    faces = self.faceCascade.detectMultiScale(gray, 1.2, 5, minSize=(100, 100))

                    if len(faces) == 0:
                        self.vote_counter = {}

                    for (x, y, w, h) in faces:
                        id_idx, confidence = self.recognizer.predict(gray[y:y+h, x:x+w])

                        if confidence < CONFIDENCE_THRESHOLD:
                            name = self.faceid_name_map.get(id_idx, "Unknown")
                                
                            self.vote_counter[name] = self.vote_counter.get(name, 0) + 1

                            if self.vote_counter[name] >= VOTE_THRESHOLD:
                                now = time.time()
                                if name not in self.last_attendance_time or (now - self.last_attendance_time[name] > COOLDOWN_SECONDS):
                                    
                                    mssv = self.get_mssv_of(name)
                                    curr_time_str = datetime.now().strftime('%H:%M:%S')
                                    # Request update thông tin sang UI
                                    self.ui.after(0, self.ui.update_student_info, name, mssv, curr_time_str, "Đang chờ thẻ...")
                                    
                                    # ---- XỬ LÝ GIAO TIẾP ARDUINO ----
                                    expected_uid = self.get_rfid_uid_of(name)
                                    if self.ser and expected_uid:
                                        self.ser.write(b'F')  # Gửi xác nhận khuôn mặt
                                        start_wait = time.time()
                                        result = "timeout"
                                        success_time = None
                                        
                                        while time.time() - start_wait < 10: # Timeout 10 giây chờ thẻ
                                            if self.ser.in_waiting > 0:
                                                line = self.ser.readline().decode('utf-8').strip()
                                                if line.startswith("UID:"):
                                                    received_uid = line[4:].strip().upper()
                                                    if received_uid == expected_uid:
                                                        # UID khớp → gửi lệnh mở cửa
                                                        self.ser.write(b'O')
                                                        ok_wait = time.time()
                                                        while time.time() - ok_wait < 5:
                                                            if self.ser.in_waiting > 0:
                                                                ok_line = self.ser.readline().decode('utf-8').strip()
                                                                if ok_line == "OK":
                                                                    result = "success"
                                                                    success_time = datetime.now()
                                                                    break
                                                            time.sleep(0.05)
                                                    else:
                                                        result = "wrong_card"
                                                        self.ui.after(0, self.ui.update_student_info, name, mssv, datetime.now().strftime('%H:%M:%S'), f"Sai thẻ (UID: {received_uid})")
                                                    break
                                            time.sleep(0.05)

                                        if result == "success":
                                            success_time_str = success_time.strftime('%H:%M:%S')
                                            self.log_attendance(name, success_time)
                                            self.ui.after(0, self.ui.update_student_info, name, mssv, success_time_str, "Thành công (OK)")
                                            self.vote_counter = {}
                                        elif result == "timeout":
                                            self.ui.after(0, self.ui.update_student_info, name, mssv, datetime.now().strftime('%H:%M:%S'), "Thất bại (Timeout)")
                                            self.vote_counter[name] = 0
                                        else:  # wrong_card
                                            self.vote_counter[name] = 0
                                    else:
                                        # Không có Arduino hoặc chưa đăng ký thẻ → KHÔNG cho điểm danh
                                        if not self.ser:
                                            self.ui.after(0, self.ui.update_student_info, name, mssv, datetime.now().strftime('%H:%M:%S'), "Lỗi: Không kết nối Arduino")
                                        else:
                                            self.ui.after(0, self.ui.update_student_info, name, mssv, datetime.now().strftime('%H:%M:%S'), "Lỗi: Chưa đăng ký thẻ RFID")
                                        self.vote_counter[name] = 0

                                display_name = f"{name} - Auth..."
                                color = (0, 255, 255)
                            else:
                                display_name = f"Scanning {name}... {self.vote_counter[name]}/{VOTE_THRESHOLD}"
                                color = (255, 255, 0)
                        else:
                            display_name = "Unknown"
                            color = (0, 0, 255)

                        cv2.rectangle(img, (x, y), (x+w, y+h), color, 2)
                        cv2.putText(img, display_name, (x+5, y-10), self.font, 0.7, color, 2)
            except Exception as e:
                pass # Chống đọng lỗi frame hỏng

            # Đẩy video frame lên UI
            self.push_image_to_ui(img)
            time.sleep(0.03) # Giới hạn max ~30fps để giảm tải CPU

    def push_image_to_ui(self, cv_img):
        cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(cv_img)
        
        # Bắt kích thước hiện tại của khung camera
        img_width = self.ui.camera_frame.winfo_width()
        img_height = self.ui.camera_frame.winfo_height()
        
        if img_width < 100 or img_height < 100:
            img_width, img_height = 640, 360 # Kích thước tạm nếu load chưa xong
            
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(img_width-20, img_height-20))
        
        # Sử dụng .after của tkinter để update luồng giao diện an toàn
        self.ui.after(0, self.ui.update_camera_image, ctk_img)

if __name__ == "__main__":
    app = AttendanceApp()
    app.mainloop()
