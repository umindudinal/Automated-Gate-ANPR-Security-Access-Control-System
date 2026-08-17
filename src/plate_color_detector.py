import cv2
import numpy as np

class PlateColorDetector:
    def __init__(self):
        # HSV Color ranges for Sri Lankan Number Plates
        # Yellow Rear Plate HSV Range
        self.yellow_lower = np.array([12, 70, 100], dtype=np.uint8)
        self.yellow_upper = np.array([38, 255, 255], dtype=np.uint8)

        # White Front Plate HSV Range
        self.white_lower = np.array([0, 0, 150], dtype=np.uint8)
        self.white_upper = np.array([180, 60, 255], dtype=np.uint8)

    def detect_color(self, crop_image):
        """
        Analyzes cropped license plate image to distinguish between:
        - 'YELLOW': Rear License Plate -> Vehicle Gate ENTRY (ඇතුල් වීම)
        - 'WHITE':  Front License Plate -> Vehicle Gate EXIT (පිට වීම)

        Returns tuple: (color_code, direction_label, confidence_score)
        """
        if crop_image is None or crop_image.size == 0:
            return ("YELLOW", "Rear / Entry", 0.50)

        try:
            hsv = cv2.cvtColor(crop_image, cv2.COLOR_BGR2HSV)
            total_pixels = hsv.shape[0] * hsv.shape[1]
            if total_pixels == 0:
                return ("YELLOW", "Rear / Entry", 0.50)

            # Create masks for Yellow and White
            yellow_mask = cv2.inRange(hsv, self.yellow_lower, self.yellow_upper)
            white_mask = cv2.inRange(hsv, self.white_lower, self.white_upper)

            yellow_pixels = cv2.countNonZero(yellow_mask)
            white_pixels = cv2.countNonZero(white_mask)

            yellow_ratio = yellow_pixels / float(total_pixels)
            white_ratio = white_pixels / float(total_pixels)

            # Sri Lankan Rear Yellow Plate Detection Logic:
            # Yellow plates have a strong yellow saturation & hue profile.
            if yellow_ratio > 0.08 and yellow_ratio >= (white_ratio * 0.35):
                score = round(min(yellow_ratio * 2.5, 1.0), 2)
                return ("YELLOW", "Rear / Entry", score)
            else:
                score = round(min(white_ratio * 1.5, 1.0), 2)
                return ("WHITE", "Front / Exit", score)

        except Exception as e:
            print(f"[Plate Color Detect Error]: {e}")
            return ("YELLOW", "Rear / Entry", 0.50)
