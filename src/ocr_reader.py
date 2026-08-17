import easyocr
import cv2
import re
import numpy as np
import config

class OCRReader:
    def __init__(self, confidence_threshold=config.OCR_CONFIDENCE_THRESHOLD):
        # Initialize EasyOCR reader for English uppercase letters & numbers
        self.reader = easyocr.Reader(['en'], gpu=False)
        self.confidence_threshold = confidence_threshold
        self.provinces = config.PROVINCE_CODES
        self.default_province = config.DEFAULT_PROVINCE

    def preprocess_image_pipelines(self, cropped_img):
        """
        Multi-Pipeline Preprocessing:
        Generates 3 contrast/binarization variations of the cropped plate image.
        EasyOCR evaluates all 3 pipelines, picking the cleanest reading.
        """
        if cropped_img is None or cropped_img.size == 0:
            return []

        # 1. Resize to standard high resolution
        height, width = cropped_img.shape[:2]
        if height < 80 or width < 160:
            scale = max(160 / width, 80 / height)
            cropped_img = cv2.resize(cropped_img, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_CUBIC)

        # Convert to Grayscale
        gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY) if len(cropped_img.shape) == 3 else cropped_img

        # Pipeline A: CLAHE + Bilateral Filter (Normal contrast)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced_a = clahe.apply(gray)
        filtered_a = cv2.bilateralFilter(enhanced_a, 9, 75, 75)

        # Pipeline B: Adaptive Thresholding (Crisp binarized letters)
        filtered_b = cv2.adaptiveThreshold(
            filtered_a, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Pipeline C: Otsu Thresholding
        _, filtered_c = cv2.threshold(filtered_a, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return [filtered_a, filtered_b, filtered_c]

    def correct_ocr_characters(self, text):
        """
        Advanced Sri Lankan License Plate Character Cleansing Engine:
        Applies domain-specific rules for Sri Lankan letters and digits.
        """
        text = re.sub(r'[^A-Z0-9]', '', text.upper())
        if len(text) < 4:
            return text

        # Extract last 4 positions as digits if possible
        numbers_part = text[-4:]
        letters_part = text[:-4]

        # Strip trailing digits from letters part
        letters_part = re.sub(r'[0-9]+$', '', letters_part)

        # 1. In digit section (last 4 characters): strictly map letters to digits
        numbers_part = numbers_part.replace('O', '0').replace('S', '5').replace('I', '1').replace('Z', '2').replace('B', '8').replace('G', '6').replace('T', '7').replace('Q', '9')

        # 2. In letter section: strictly map digits to letters
        letters_part = letters_part.replace('0', 'O').replace('5', 'S').replace('1', 'I').replace('8', 'B').replace('6', 'G')

        # 3. Strip leading single noise characters before valid province code (e.g. DWPCAB -> WPCAB, IWPLN -> WPLN)
        for prov in self.provinces:
            m = re.search(r'(?:^|[A-Z0-9])(' + prov + r'[A-Z0-9]+)$', letters_part)
            if m:
                letters_part = m.group(1)
                break

        # 4. Fix common corrupted province prefixes
        if letters_part.startswith('NH') or letters_part.startswith('NM'):
            letters_part = 'NW' + letters_part[2:]
        elif letters_part.startswith('VV') or letters_part.startswith('VP') or letters_part.startswith('0P') or letters_part.startswith('W1'):
            letters_part = 'WP' + letters_part[2:]

        # 5. Fix common Sri Lankan series letter misreads
        # 'LM' -> 'LN' (common OCR misread on LN series)
        letters_part = re.sub(r'LM$', 'LN', letters_part)
        
        # 6. Sri Lankan plates have 2 or 3 main series letters (e.g., CAB, CBG, CAD, LN, PK, KMG)
        if len(letters_part) > 5:
            # Drop extra noise prefix
            letters_part = letters_part[-3:]
        elif len(letters_part) == 4 and not (letters_part[:2] in self.provinces):
            letters_part = letters_part[-3:]

        return f"{letters_part}{numbers_part}"

    def validate_and_format_plate(self, raw_text):
        """Validates and formats raw_text strictly into Official Sri Lankan Plate Standard."""
        clean_text = self.correct_ocr_characters(raw_text)

        # 1. Attempt Sri Lankan Modern format match: [Province] [2-3 Letters] [4 Digits]
        # Example: WPCAB6036 -> WP CAB - 6036, WPLN8132 -> WP LN - 8132
        match_modern = re.match(r'^(WP|NW|CP|SP|UP|SG|NC|EP|NP)?([A-Z]{2,3})(\d{4})$', clean_text)
        if match_modern:
            province, letters, digits = match_modern.groups()
            prov_str = province if province else self.default_province
            return f"{prov_str} {letters} - {digits}"

        # 2. Attempt Sri Lankan Vintage format match: [Province] [1-3 Digits/Letters] [4 Digits]
        # Example: 646036 -> 64 - 6036 or GACAB6036 -> GA - 6036
        match_vintage = re.match(r'^(WP|NW|CP|SP|UP|SG|NC|EP|NP)?([0-9]{1,3}|[A-Z]{1,2})(\d{4})$', clean_text)
        if match_vintage:
            province, section, digits = match_vintage.groups()
            prov_str = f"{province} " if province else ""
            return f"{prov_str}{section} - {digits}"

        # 3. Fallback for 2-3 letters + 4 digits: ensure Province prefix is added for standard layout
        if len(clean_text) >= 6 and re.search(r'\d{4}$', clean_text):
            letters = clean_text[:-4]
            digits = clean_text[-4:]
            if 2 <= len(letters) <= 3:
                return f"{self.default_province} {letters} - {digits}"

        return None

    def read_text(self, cropped_image):
        """
        Runs multi-pipeline preprocessing, reads text via EasyOCR across all pipelines,
        and returns the candidate plate with the HIGHEST confidence score matching Sri Lankan standard.
        """
        pipelines = self.preprocess_image_pipelines(cropped_image)
        if not pipelines:
            return []

        candidates = []

        for img in pipelines:
            results = self.reader.readtext(img, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
            if not results:
                continue

            raw_text = ""
            total_prob = 0.0

            for (_, text, prob) in results:
                raw_text += text
                total_prob += prob

            avg_confidence = total_prob / len(results) if results else 0.0

            if avg_confidence >= self.confidence_threshold:
                formatted_plate = self.validate_and_format_plate(raw_text)
                if formatted_plate:
                    candidates.append((formatted_plate, avg_confidence))

        if not candidates:
            return []

        # Return candidate with maximum confidence score among all preprocessing pipelines
        best_candidate = max(candidates, key=lambda c: c[1])
        return [best_candidate]