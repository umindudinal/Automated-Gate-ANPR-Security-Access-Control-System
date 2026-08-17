import cv2
import os
from ultralytics import YOLO

class LicensePlateDetector:
    VEHICLE_CLASS_MAP = {
        2: "Car",
        3: "Bike",
        5: "Bus",
        7: "Truck"
    }

    def __init__(self, model_path='models/license_plate_detector.pt', vehicle_model_path='yolov8n.pt'):
        # License Plate Model
        if not os.path.exists(model_path):
            print(f"\n[දැනුම්දීම]: '{model_path}' සොයාගත නොහැක.")
            print("ඒ වෙනුවට සාමාන්‍ය YOLOv8 මාදිලිය භාගත කරමින් පවතී...\n")
            self.model = YOLO('yolov8n.pt') 
        else:
            self.model = YOLO(model_path)

        # Vehicle Classification Model (COCO Pretrained YOLOv8)
        self.vehicle_model = YOLO(vehicle_model_path)

    def detect_vehicles(self, image):
        """Detects vehicle bounding boxes and their class labels in image."""
        results = self.vehicle_model(image, verbose=False)
        vehicles = []

        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                if cls_id in self.VEHICLE_CLASS_MAP:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    vtype = self.VEHICLE_CLASS_MAP[cls_id]
                    
                    # Distinguish Van vs Car based on aspect ratio if car class
                    bw = x2 - x1
                    bh = y2 - y1
                    if vtype == "Car" and bh > 0 and (bw / bh) < 1.35 and (bw * bh) > 40000:
                        vtype = "Van"

                    vehicles.append({'bbox': (x1, y1, x2, y2), 'type': vtype})

        return vehicles

    def detect_and_crop(self, image):
        """
        Detects license plates and matches each plate to its parent vehicle type.
        Returns list of tuples: (cropped_img, vehicle_type, (px1, py1, px2, py2))
        """
        # 1. Detect overall vehicles in frame
        vehicles = self.detect_vehicles(image)

        # 2. Detect license plates
        results = self.model(image, verbose=False)
        crops = []

        for result in results:
            for box in result.boxes:
                px1, py1, px2, py2 = map(int, box.xyxy[0])
                cropped_img = image[py1:py2, px1:px2]

                # Find containing/overlapping vehicle for this plate
                plate_cx = (px1 + px2) / 2.0
                plate_cy = (py1 + py2) / 2.0

                matched_type = "Car"  # Default fallback
                for v in vehicles:
                    vx1, vy1, vx2, vy2 = v['bbox']
                    if vx1 <= plate_cx <= vx2 and vy1 <= plate_cy <= vy2:
                        matched_type = v['type']
                        break

                crops.append((cropped_img, matched_type, (px1, py1, px2, py2)))

        return crops