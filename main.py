import cv2
import os
import time
from datetime import datetime
import config
from src.detector import LicensePlateDetector
from src.ocr_reader import OCRReader
from src.database import Database
from src.plate_buffer import PlateBuffer

def main():
    video_path = os.path.join(config.INPUT_VIDEOS_DIR, 'test_video.mp4')
    
    if not os.path.exists(video_path):
        print(f"\n[දෝෂයකි]: වීඩියෝවක් '{video_path}' හි සොයාගත නොහැක.")
        return

    print("\n=======================================================")
    print("   Automated Gate ANPR Security System (Enterprise Edition)")
    print("=======================================================\n")
    print("පද්ධතිය ආරම්භ වෙමින් පවතී. කරුණාකර රැඳී සිටින්න...\n")

    detector = LicensePlateDetector(model_path=config.YOLO_MODEL_PATH)
    ocr = OCRReader(confidence_threshold=config.OCR_CONFIDENCE_THRESHOLD)
    db = Database(csv_file=config.CSV_LOG_PATH, db_file=config.SQLITE_DB_PATH)
    buffer = PlateBuffer(window_size=config.VOTING_WINDOW_FRAMES, cooldown_seconds=config.PLATE_COOLDOWN_SECONDS)

    cap = cv2.VideoCapture(video_path)
    
    frame_count = 0
    total_logged_vehicles = 0
    recent_logs = []
    
    # Store candidate crops for audit trail save
    latest_crops = {}

    print("\n[වීඩියෝව පරීක්ෂා කිරීම ආරම්භ විය. නවතාලීමට 'q' ඔබන්න]")
    print("-" * 60)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Process every Nth frame for performance optimization
        if frame_count % config.FRAME_SKIP_RATE != 0:
            continue

        # Detect license plates & parent vehicle types using YOLOv8
        crops = detector.detect_and_crop(frame)

        for crop, vtype, bbox in crops:
            px1, py1, px2, py2 = bbox
            
            # Draw RED Bounding Box around detected plate box (BGR: (0, 0, 255))
            cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 255), 3)

            results = ocr.read_text(crop)
            for (plate_text, confidence) in results:
                # Add to sliding window voting buffer with vehicle_type
                buffer.add_detection(plate_text, confidence, vehicle_type=vtype)
                latest_crops[plate_text] = crop

                # Render label badge above the red bounding box
                label = f"{plate_text} [{vtype}]"
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
                lbl_y = max(py1 - 10, 25)
                
                # Label background rectangle (Red)
                cv2.rectangle(frame, (px1, lbl_y - h - 10), (px1 + w + 12, lbl_y + 4), (0, 0, 255), -1)
                
                # Text inside label (White)
                cv2.putText(frame, label, (px1 + 6, lbl_y - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)


        # Evaluate voting buffer for winner
        winner = buffer.process_buffer_and_get_winner()
        if winner:
            winning_plate, winning_conf, winning_vtype = winner
            winning_crop = latest_crops.get(winning_plate, None)
            
            # Log to DB/CSV and save crop artifact
            event_type, crop_path, plate_col = db.log_vehicle(winning_plate, vehicle_type=winning_vtype, confidence=winning_conf, crop_image=winning_crop)
            if event_type != "IGNORED":
                total_logged_vehicles += 1
                recent_logs.append((winning_plate, winning_conf, winning_vtype, event_type, plate_col, datetime.now().strftime("%H:%M:%S")))
                if len(recent_logs) > 3:
                    recent_logs.pop(0)

        # Render Modern UI Overlay on OpenCV Display Window
        display_frame = cv2.resize(frame, (960, 540))
        
        # Header banner
        cv2.rectangle(display_frame, (0, 0), (960, 45), (15, 23, 42), -1)
        cv2.putText(display_frame, "AUTOMATED GATE ANPR SECURITY SYSTEM | LIVE GATE MONITORING", (15, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        # Counter badge
        cv2.rectangle(display_frame, (730, 8), (945, 38), (37, 99, 235), -1)
        cv2.putText(display_frame, f"Logged: {total_logged_vehicles} Vehicles", (740, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # Recent Log panel (Bottom Overlay)
        if recent_logs:
            cv2.rectangle(display_frame, (10, 450), (620, 530), (0, 0, 0), -1)
            cv2.rectangle(display_frame, (10, 450), (620, 530), (37, 99, 235), 2)
            cv2.putText(display_frame, "LAST DETECTED VEHICLE GATE ACTION:", (20, 470),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (148, 163, 184), 1)
            
            last_plate, last_conf, last_vtype, last_evt, last_col, last_time = recent_logs[-1]
            evt_color = (52, 211, 153) if last_evt == "ENTRY" else (251, 146, 60)
            tag_label = "YELLOW-ENTRY" if last_col == "YELLOW" else "WHITE-EXIT"
            cv2.putText(display_frame, f"{last_plate} [{last_vtype}] ({tag_label}) at {last_time}", (20, 505),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.58, evt_color, 2)

        cv2.imshow('Automated Gate ANPR Live Feed', display_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("-" * 60)
    print(f"\nවීඩියෝ පරීක්ෂාව සාර්ථකව අවසන් විය! මුළු සටහන් කළ වාහන ගණන: {total_logged_vehicles}")

if __name__ == "__main__":
    main()