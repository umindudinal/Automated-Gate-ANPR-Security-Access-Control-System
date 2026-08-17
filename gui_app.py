import os
import sys
import time
import threading
import subprocess
from datetime import datetime
import cv2
import pandas as pd
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

# Ensure workspace root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import config
from src.detector import LicensePlateDetector
from src.ocr_reader import OCRReader
from src.database import Database
from src.plate_buffer import PlateBuffer

# Set CustomTkinter Appearance Mode to LIGHT
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class CampusANPRApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Configuration
        self.title("Automated Gate ANPR Security & Access Control System")
        self.geometry("1450x880")
        self.minsize(1180, 740)
        self.configure(fg_color="#F8FAFC")  # Light Slate background

        # Core Modules
        self.detector = LicensePlateDetector(model_path=config.YOLO_MODEL_PATH)
        self.ocr = OCRReader(confidence_threshold=config.OCR_CONFIDENCE_THRESHOLD)
        self.db = Database(csv_file=config.CSV_LOG_PATH, db_file=config.SQLITE_DB_PATH)
        self.buffer = PlateBuffer(window_size=config.VOTING_WINDOW_FRAMES, cooldown_seconds=config.PLATE_COOLDOWN_SECONDS)

        # State Variables
        self.is_monitoring = False
        self.video_source = os.path.join(config.INPUT_VIDEOS_DIR, 'test_video.mp4')
        self.cap = None
        self.video_thread = None
        self.latest_crops = {}
        self.active_view_mode = "Master Register"

        # Build Light Mode UI Structure
        self._build_header()
        self._build_main_layout()

        # Start Live Clock and Periodic DB Refresh
        self._update_clock()
        self.refresh_logs()

    # -------------------------------------------------------------
    # 1. HEADER BAR
    # -------------------------------------------------------------
    def _build_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=12, border_width=1, border_color="#E2E8F0", height=70)
        header_frame.pack(fill="x", padx=20, pady=(15, 10))

        # Title & Subtitle
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=10)

        main_title = ctk.CTkLabel(
            title_box, 
            text="🚘 AUTOMATED GATE ANPR SECURITY SYSTEM", 
            font=ctk.CTkFont(family="Inter", size=20, weight="bold"),
            text_color="#0F172A"
        )
        main_title.pack(anchor="w")

        sub_title = ctk.CTkLabel(
            title_box, 
            text="Enterprise Gate Access Control (Yellow Rear Entry / White Front Exit) & Presence Audit System", 
            font=ctk.CTkFont(family="Inter", size=12),
            text_color="#64748B"
        )
        sub_title.pack(anchor="w")

        # Right Header Widgets (Clock & Status Badge)
        right_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_box.pack(side="right", padx=20, pady=10)

        self.status_badge = ctk.CTkLabel(
            right_box,
            text="● STANDBY",
            font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
            fg_color="#F1F5F9",
            text_color="#475569",
            corner_radius=8,
            width=120,
            height=32
        )
        self.status_badge.pack(side="right", padx=(10, 0))

        self.clock_label = ctk.CTkLabel(
            right_box,
            text="00:00:00 AM",
            font=ctk.CTkFont(family="Inter", size=14, weight="bold"),
            text_color="#1E293B"
        )
        self.clock_label.pack(side="right", padx=10)

    # -------------------------------------------------------------
    # 2. MAIN LAYOUT (LEFT: VIDEO, RIGHT: METRICS & TABLES)
    # -------------------------------------------------------------
    def _build_main_layout(self):
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=5)

        # Left Column: Video Feed & Controls
        left_col = ctk.CTkFrame(main_container, fg_color="#FFFFFF", corner_radius=12, border_width=1, border_color="#E2E8F0", width=580)
        left_col.pack(side="left", fill="both", expand=False, padx=(0, 10), pady=5)

        # Right Column: Metrics, Filter Controls, Log Register, Audit Trail
        right_col = ctk.CTkFrame(main_container, fg_color="transparent")
        right_col.pack(side="right", fill="both", expand=True, padx=(10, 0), pady=5)

        self._build_video_section(left_col)
        self._build_metrics_and_tables(right_col)

    # -------------------------------------------------------------
    # 3. VIDEO SECTION (LEFT COLUMN)
    # -------------------------------------------------------------
    def _build_video_section(self, parent):
        sec_title_frame = ctk.CTkFrame(parent, fg_color="transparent")
        sec_title_frame.pack(fill="x", padx=15, pady=(15, 10))

        sec_title = ctk.CTkLabel(
            sec_title_frame,
            text="📹 Live Gate Video Stream",
            font=ctk.CTkFont(family="Inter", size=15, weight="bold"),
            text_color="#0F172A"
        )
        sec_title.pack(side="left")

        res_label = ctk.CTkLabel(
            sec_title_frame,
            text="Resolution: 640x360",
            font=ctk.CTkFont(family="Inter", size=11),
            text_color="#94A3B8"
        )
        res_label.pack(side="right")

        # Video Canvas Card
        video_card = ctk.CTkFrame(parent, fg_color="#F8FAFC", corner_radius=10, border_width=1, border_color="#E2E8F0")
        video_card.pack(fill="both", expand=True, padx=15, pady=5)

        self.video_label = ctk.CTkLabel(
            video_card,
            text="[ Camera / Video Standby ]\nClick 'Start Monitoring' to launch live gate feed",
            font=ctk.CTkFont(family="Inter", size=14),
            text_color="#64748B",
            fg_color="#E2E8F0",
            corner_radius=8
        )
        self.video_label.pack(fill="both", expand=True, padx=10, pady=10)

        # Video Action Controls Bar
        ctrl_frame = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=15, pady=15)

        self.btn_start = ctk.CTkButton(
            ctrl_frame,
            text="▶ Start Monitoring",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            text_color="#FFFFFF",
            corner_radius=8,
            height=38,
            command=self.start_monitoring
        )
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.btn_stop = ctk.CTkButton(
            ctrl_frame,
            text="⏹ Stop Feed",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color="#DC2626",
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            corner_radius=8,
            height=38,
            state="disabled",
            command=self.stop_monitoring
        )
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=5)

        self.btn_browse = ctk.CTkButton(
            ctrl_frame,
            text="📁 Select File",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            text_color="#FFFFFF",
            corner_radius=8,
            height=38,
            command=self.select_video_file
        )
        self.btn_browse.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # Secondary Actions Frame (Launch Web Dashboard & Clear Logs)
        sec_action_frame = ctk.CTkFrame(parent, fg_color="transparent")
        sec_action_frame.pack(fill="x", padx=15, pady=(0, 15))

        dash_btn = ctk.CTkButton(
            sec_action_frame,
            text="📊 Web Dashboard",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color="#4F46E5",
            hover_color="#4338CA",
            text_color="#FFFFFF",
            corner_radius=8,
            height=38,
            command=self.launch_streamlit_dashboard
        )
        dash_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        purge_btn = ctk.CTkButton(
            sec_action_frame,
            text="🗑️ Clear All Logs",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color="#EF4444",
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            corner_radius=8,
            height=38,
            command=self.purge_all_logs
        )
        purge_btn.pack(side="left", expand=True, fill="x", padx=(5, 0))


    # -------------------------------------------------------------
    # 4. METRICS & DATA REGISTRATION TABLES (RIGHT COLUMN)
    # -------------------------------------------------------------
    def _build_metrics_and_tables(self, parent):
        # Top Metrics Grid (4 Cards)
        metrics_frame = ctk.CTkFrame(parent, fg_color="transparent")
        metrics_frame.pack(fill="x", pady=(0, 10))
        metrics_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.card_total = self._create_metric_card(metrics_frame, 0, "TOTAL VISITS", "0", "#2563EB")
        self.card_inside = self._create_metric_card(metrics_frame, 1, "CURRENTLY INSIDE", "0", "#059669")
        self.card_exited = self._create_metric_card(metrics_frame, 2, "EXITED VEHICLES", "0", "#64748B")
        self.card_latest = self._create_metric_card(metrics_frame, 3, "LAST GATE ACTION", "None", "#4F46E5")

        # Table & View Selector Section
        table_card = ctk.CTkFrame(parent, fg_color="#FFFFFF", corner_radius=12, border_width=1, border_color="#E2E8F0")
        table_card.pack(fill="both", expand=True, pady=5)

        tb_header = ctk.CTkFrame(table_card, fg_color="transparent")
        tb_header.pack(fill="x", padx=15, pady=10)

        tb_title = ctk.CTkLabel(
            tb_header,
            text="📋 Directional Gate Access Register",
            font=ctk.CTkFont(family="Inter", size=15, weight="bold"),
            text_color="#0F172A"
        )
        tb_title.pack(side="left")

        # Segmented Table View Switcher
        self.seg_view = ctk.CTkSegmentedButton(
            tb_header,
            values=["Master Register", "Inside (ඇතුළත)", "Exited (පිටවූ)", "Verified (≥90%)", "Review (<90%)"],
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            selected_color="#2563EB",
            selected_hover_color="#1D4ED8",
            unselected_color="#F1F5F9",
            unselected_hover_color="#E2E8F0",
            text_color="#0F172A",
            command=self.on_table_view_changed
        )
        self.seg_view.set("Master Register")
        self.seg_view.pack(side="right")

        # Treeview Data Table (Styled for Light Theme)
        table_container = ctk.CTkFrame(table_card, fg_color="transparent")
        table_container.pack(fill="both", expand=True, padx=15, pady=5)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#FFFFFF",
            foreground="#0F172A",
            rowheight=28,
            fieldbackground="#FFFFFF",
            font=("Inter", 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#F1F5F9",
            foreground="#1E293B",
            font=("Inter", 10, "bold"),
            borderwidth=1,
            relief="flat"
        )
        style.map("Treeview", background=[("selected", "#3B82F6")], foreground=[("selected", "#FFFFFF")])

        cols = ("id", "date", "entry_time", "exit_time", "number_plate", "vehicle_type", "plate_color", "status", "duration", "confidence")
        self.tree = ttk.Treeview(table_container, columns=cols, show="headings", height=8)

        self.tree.heading("id", text="ID")
        self.tree.heading("date", text="Date")
        self.tree.heading("entry_time", text="Entry Time")
        self.tree.heading("exit_time", text="Exit Time")
        self.tree.heading("number_plate", text="License Plate")
        self.tree.heading("vehicle_type", text="Category")
        self.tree.heading("plate_color", text="Plate View (Color)")
        self.tree.heading("status", text="Gate Status")
        self.tree.heading("duration", text="Stay Duration")
        self.tree.heading("confidence", text="Confidence")

        self.tree.column("id", width=35, anchor="center")
        self.tree.column("date", width=80, anchor="center")
        self.tree.column("entry_time", width=75, anchor="center")
        self.tree.column("exit_time", width=75, anchor="center")
        self.tree.column("number_plate", width=115, anchor="w")
        self.tree.column("vehicle_type", width=75, anchor="center")
        self.tree.column("plate_color", width=120, anchor="center")
        self.tree.column("status", width=85, anchor="center")
        self.tree.column("duration", width=85, anchor="center")
        self.tree.column("confidence", width=75, anchor="center")

        tree_scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self.on_log_row_selected)

        # Audit Trail Panel (Cropped Images + Metadata)
        audit_card = ctk.CTkFrame(table_card, fg_color="#F8FAFC", corner_radius=10, border_width=1, border_color="#E2E8F0")
        audit_card.pack(fill="x", padx=15, pady=(5, 12))

        audit_card.grid_columnconfigure(2, weight=1)

        # Left Entry Crop Image Container (Yellow Rear Plate)
        crop_box_entry = ctk.CTkFrame(audit_card, fg_color="#FFFFFF", corner_radius=8, border_width=1, border_color="#CBD5E1", width=140, height=80)
        crop_box_entry.grid(row=0, column=0, padx=(10, 5), pady=10)
        crop_box_entry.grid_propagate(False)

        self.crop_entry_label = ctk.CTkLabel(
            crop_box_entry,
            text="[ 🟡 Entry Crop ]",
            font=ctk.CTkFont(family="Inter", size=10),
            text_color="#94A3B8"
        )
        self.crop_entry_label.pack(fill="both", expand=True)

        # Exit Crop Image Container (White Front Plate)
        crop_box_exit = ctk.CTkFrame(audit_card, fg_color="#FFFFFF", corner_radius=8, border_width=1, border_color="#CBD5E1", width=140, height=80)
        crop_box_exit.grid(row=0, column=1, padx=(5, 10), pady=10)
        crop_box_exit.grid_propagate(False)

        self.crop_exit_label = ctk.CTkLabel(
            crop_box_exit,
            text="[ ⚪ Exit Crop ]",
            font=ctk.CTkFont(family="Inter", size=10),
            text_color="#94A3B8"
        )
        self.crop_exit_label.pack(fill="both", expand=True)

        # Right Metadata Details
        meta_box = ctk.CTkFrame(audit_card, fg_color="transparent")
        meta_box.grid(row=0, column=2, padx=10, pady=8, sticky="nsew")

        self.lbl_audit_plate = ctk.CTkLabel(meta_box, text="Selected Plate: --", font=ctk.CTkFont(family="Inter", size=13, weight="bold"), text_color="#0F172A", anchor="w")
        self.lbl_audit_plate.pack(anchor="w")

        self.lbl_audit_status = ctk.CTkLabel(meta_box, text="Status & Category: --", font=ctk.CTkFont(family="Inter", size=11), text_color="#475569", anchor="w")
        self.lbl_audit_status.pack(anchor="w")

        self.lbl_audit_times = ctk.CTkLabel(meta_box, text="Entry: -- | Exit: --", font=ctk.CTkFont(family="Inter", size=11), text_color="#475569", anchor="w")
        self.lbl_audit_times.pack(anchor="w")

        self.lbl_audit_duration = ctk.CTkLabel(meta_box, text="Stay Duration: --", font=ctk.CTkFont(family="Inter", size=11), text_color="#475569", anchor="w")
        self.lbl_audit_duration.pack(anchor="w")

    def _create_metric_card(self, parent, col, title, value, color):
        card = ctk.CTkFrame(parent, fg_color="#FFFFFF", corner_radius=10, border_width=1, border_color="#E2E8F0")
        card.grid(row=0, column=col, padx=4, pady=4, sticky="nsew")

        val_label = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(family="Inter", size=19, weight="bold"), text_color=color)
        val_label.pack(pady=(10, 0))

        title_label = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(family="Inter", size=10, weight="bold"), text_color="#64748B")
        title_label.pack(pady=(0, 10))

        return val_label

    # -------------------------------------------------------------
    # 5. LOGIC & EVENT HANDLERS
    # -------------------------------------------------------------
    def _update_clock(self):
        now_str = datetime.now().strftime("%I:%M:%S %p")
        self.clock_label.configure(text=now_str)
        self.after(1000, self._update_clock)

    def select_video_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video Files", "*.mp4 *.avi *.mkv *.mov"), ("All Files", "*.*")]
        )
        if file_path:
            self.video_source = file_path
            messagebox.showinfo("Video Source", f"Selected Video File:\n{os.path.basename(file_path)}")

    def start_monitoring(self):
        if self.is_monitoring:
            return

        if not os.path.exists(self.video_source):
            messagebox.showerror("Error", f"Video source file not found:\n{self.video_source}")
            return

        self.cap = cv2.VideoCapture(self.video_source)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Failed to open video source.")
            return

        self.is_monitoring = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_badge.configure(text="● LIVE FEED", fg_color="#DCFCE7", text_color="#15803D")

        # Start Video Thread
        self.video_thread = threading.Thread(target=self._video_processing_worker, daemon=True)
        self.video_thread.start()

    def stop_monitoring(self):
        self.is_monitoring = False
        if self.cap and self.cap.isOpened():
            self.cap.release()

        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_badge.configure(text="● STANDBY", fg_color="#F1F5F9", text_color="#475569")
        self.video_label.configure(image="", text="[ Camera / Video Standby ]\nClick 'Start Monitoring' to launch live gate feed")

    def _video_processing_worker(self):
        frame_count = 0

        while self.is_monitoring and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame_count += 1
            if frame_count % config.FRAME_SKIP_RATE == 0:
                crops = self.detector.detect_and_crop(frame)

                for crop, vtype, bbox in crops:
                    px1, py1, px2, py2 = bbox
                    cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 255), 3)

                    results = self.ocr.read_text(crop)
                    for (plate_text, confidence) in results:
                        self.buffer.add_detection(plate_text, confidence, vehicle_type=vtype)
                        self.latest_crops[plate_text] = crop

                        label = f"{plate_text} [{vtype}]"
                        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
                        lbl_y = max(py1 - 10, 25)
                        cv2.rectangle(frame, (px1, lbl_y - h - 10), (px1 + w + 12, lbl_y + 4), (0, 0, 255), -1)
                        cv2.putText(frame, label, (px1 + 6, lbl_y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

                winner = self.buffer.process_buffer_and_get_winner()
                if winner:
                    winning_plate, winning_conf, winning_vtype = winner
                    winning_crop = self.latest_crops.get(winning_plate, None)
                    
                    event_type, crop_path, plate_col = self.db.log_vehicle(winning_plate, vehicle_type=winning_vtype, confidence=winning_conf, crop_image=winning_crop)
                    if event_type != "IGNORED":
                        self.after(0, self.refresh_logs)

            # Resize frame for GUI display label
            display_frame = cv2.resize(frame, (540, 310))
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(540, 310))

            self.after(0, self._update_video_label, ctk_img)
            time.sleep(0.03)

    def _update_video_label(self, ctk_img):
        if self.is_monitoring:
            self.video_label.configure(image=ctk_img, text="")

    def on_table_view_changed(self, value):
        self.active_view_mode = value
        self.refresh_logs()

    def refresh_logs(self):
        # Clear existing Treeview items
        for item in self.tree.get_children():
            self.tree.delete(item)

        all_logs = self.db.get_all_logs()
        inside_logs = self.db.get_inside_logs()
        exited_logs = self.db.get_exited_logs()
        verified_logs = self.db.get_verified_logs()
        review_logs = self.db.get_review_logs()

        # Update Top Metric Cards
        self.card_total.configure(text=str(len(all_logs)))
        self.card_inside.configure(text=str(len(inside_logs)))
        self.card_exited.configure(text=str(len(exited_logs)))

        if all_logs:
            last_rec = all_logs[0]
            # row format: id, date, time, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, exit_date, plate_color
            last_p, last_vt, last_st = last_rec[4], last_rec[5], last_rec[6]
            self.card_latest.configure(text=f"{last_p} ({last_st})")
        else:
            self.card_latest.configure(text="None")

        # Select data list based on view switcher
        if self.active_view_mode == "Inside (ඇතුළත)":
            display_logs = inside_logs
        elif self.active_view_mode == "Exited (පිටවූ)":
            display_logs = exited_logs
        elif self.active_view_mode == "Verified (≥90%)":
            display_logs = verified_logs
        elif self.active_view_mode == "Review (<90%)":
            display_logs = review_logs
        else:
            display_logs = all_logs

        for idx, row in enumerate(display_logs):
            rec_id, entry_date, entry_time, exit_time, plate, vtype, status, duration, conf, crop_entry, crop_exit, exit_date, plate_color = row
            conf_val = float(conf)
            exit_display = exit_time if exit_time else "-"
            status_display = "● INSIDE" if status == "INSIDE" else "✓ EXITED"
            color_badge = "🟡 Yellow (Rear)" if plate_color == "YELLOW" else "⚪ White (Front)"

            self.tree.insert(
                "",
                "end",
                values=(rec_id, entry_date, entry_time, exit_display, plate, vtype, color_badge, status_display, duration, f"{conf_val:.1f}%"),
                tags=(crop_entry, crop_exit)
            )

    def on_log_row_selected(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        item = selected_items[0]
        vals = self.tree.item(item, "values")
        tags = self.tree.item(item, "tags")

        rec_id = vals[0]
        entry_time = vals[2]
        exit_time = vals[3]
        plate_str = vals[4]
        vtype_str = vals[5]
        color_badge = vals[6]
        status_str = vals[7]
        duration_str = vals[8]
        conf_str = vals[9]
        crop_entry = tags[0] if tags and len(tags) > 0 else ""
        crop_exit = tags[1] if tags and len(tags) > 1 else ""

        self.lbl_audit_plate.configure(text=f"Selected Plate: {plate_str}")
        self.lbl_audit_status.configure(text=f"Status: {status_str} | View: {color_badge} | Category: {vtype_str}")
        self.lbl_audit_times.configure(text=f"Entry Time: {entry_time} | Exit Time: {exit_time}")
        self.lbl_audit_duration.configure(text=f"Stay Duration: {duration_str} | OCR Conf: {conf_str}")

        # Render Entry Crop Preview Image
        if crop_entry and os.path.exists(crop_entry):
            try:
                img_e = Image.open(crop_entry)
                ctk_e = ctk.CTkImage(light_image=img_e, dark_image=img_e, size=(130, 65))
                self.crop_entry_label.configure(image=ctk_e, text="")
            except Exception:
                self.crop_entry_label.configure(image="", text="[ Entry Error ]")
        else:
            self.crop_entry_label.configure(image="", text="[ No Entry Crop ]")

        # Render Exit Crop Preview Image
        if crop_exit and os.path.exists(crop_exit):
            try:
                img_x = Image.open(crop_exit)
                ctk_x = ctk.CTkImage(light_image=img_x, dark_image=img_x, size=(130, 65))
                self.crop_exit_label.configure(image=ctk_x, text="")
            except Exception:
                self.crop_exit_label.configure(image="", text="[ Exit Error ]")
        else:
            self.crop_exit_label.configure(image="", text="[ Not Exited Yet ]")

    def launch_streamlit_dashboard(self):
        try:
            streamlit_cmd = [sys.executable, "-m", "streamlit", "run", "ui/app.py"]
            subprocess.Popen(streamlit_cmd, cwd=BASE_DIR)
            messagebox.showinfo("Web Dashboard", "Launching Streamlit Dashboard in your default browser...")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Streamlit:\n{e}")

    def purge_all_logs(self):
        confirm = messagebox.askyesno(
            "Confirm Data Purge",
            "⚠️ ARE YOU SURE?\n\nThis will permanently delete all vehicle logs from MySQL, SQLite, CSV files, and purge all cropped plate images.\n\nThis action CANNOT be undone!",
            icon="warning"
        )
        if confirm:
            self.db.clear_all_logs()
            self.refresh_logs()
            self.lbl_audit_plate.configure(text="Selected Plate: --")
            self.lbl_audit_status.configure(text="Status & Category: --")
            self.lbl_audit_times.configure(text="Entry: -- | Exit: --")
            self.lbl_audit_duration.configure(text="Stay Duration: --")
            self.crop_entry_label.configure(image="", text="[ Entry Crop ]")
            self.crop_exit_label.configure(image="", text="[ Exit Crop ]")
            messagebox.showinfo("Purge Complete", "All vehicle logs and crop image files have been purged successfully!")


    def on_closing(self):
        self.stop_monitoring()
        self.destroy()


if __name__ == "__main__":
    app = CampusANPRApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
