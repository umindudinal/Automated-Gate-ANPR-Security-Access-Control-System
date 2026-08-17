import time
import re
from difflib import SequenceMatcher
from collections import defaultdict
import config

class PlateBuffer:
    def __init__(self, window_size=config.VOTING_WINDOW_FRAMES, cooldown_seconds=config.PLATE_COOLDOWN_SECONDS):
        self.window_size = window_size
        self.cooldown_seconds = cooldown_seconds
        
        # Buffer structure: list of (plate_text, confidence, vehicle_type)
        self.candidate_buffer = []
        
        # Cooldown dictionary: identifier -> timestamp of last log
        self.cooldown_dict = {}

    def similarity_ratio(self, a, b):
        """Computes string similarity ratio between two plate strings."""
        return SequenceMatcher(None, a, b).ratio()

    def is_in_cooldown(self, candidate_plate, current_time=None):
        """
        Smart Cooldown Check:
        Checks exact match, matching trailing digits, or >70% string similarity 
        against recently logged plates within the cooldown window.
        """
        if current_time is None:
            current_time = time.time()

        cand_digits = re.search(r'\d{3,4}$', candidate_plate)
        cand_digit_str = cand_digits.group(0) if cand_digits else None

        for logged_plate, last_time in list(self.cooldown_dict.items()):
            elapsed = current_time - last_time
            if elapsed < self.cooldown_seconds:
                # 1. Exact string match or matching trailing digits identifier
                if candidate_plate == logged_plate or (cand_digit_str and cand_digit_str == logged_plate):
                    return True
                
                # 2. Matching trailing digits against logged plate string
                logged_digits = re.search(r'\d{3,4}$', logged_plate)
                if cand_digit_str and logged_digits and cand_digit_str == logged_digits.group(0):
                    return True
                
                # 3. High string similarity ratio (> 70%)
                if self.similarity_ratio(candidate_plate, logged_plate) >= 0.70:
                    return True
            else:
                # Remove expired cooldown entry
                self.cooldown_dict.pop(logged_plate, None)

        return False

    def add_detection(self, plate_text, confidence, vehicle_type="Car", current_time=None):
        """Adds a detection to the sliding voting buffer if not in smart cooldown."""
        if not self.is_in_cooldown(plate_text, current_time):
            self.candidate_buffer.append((plate_text, confidence, vehicle_type))

    def process_buffer_and_get_winner(self, current_time=None):
        """
        Groups candidate detections by vehicle (trailing 4 digits / similarity),
        and returns the candidate string with the MAXIMUM confidence score.
        """
        if not self.candidate_buffer:
            return None

        if current_time is None:
            current_time = time.time()

        # Group candidate detections by vehicle
        groups = defaultdict(list)

        for plate, conf, vtype in self.candidate_buffer:
            if not self.is_in_cooldown(plate, current_time):
                digits = re.search(r'\d{3,4}$', plate)
                group_key = digits.group(0) if digits else plate
                groups[group_key].append((plate, conf, vtype))

        if not groups:
            self.candidate_buffer.clear()
            return None

        # Find the group with the highest total accumulated confidence
        best_group_key = max(groups.keys(), key=lambda g: sum(item[1] for item in groups[g]))
        group_items = groups[best_group_key]

        # From the winning group, select the candidate string with the MAXIMUM confidence score!
        best_item = max(group_items, key=lambda item: item[1])
        best_plate, max_confidence, winning_vtype = best_item

        # Require minimum confidence threshold (>= 0.60) or at least 2 votes
        if len(group_items) >= 2 or max_confidence >= 0.60:
            # Register both exact plate and digits key in cooldown dictionary to block all variations
            self.cooldown_dict[best_plate] = current_time
            if re.search(r'\d{3,4}$', best_plate):
                digits_str = re.search(r'\d{3,4}$', best_plate).group(0)
                self.cooldown_dict[digits_str] = current_time

            self.candidate_buffer.clear()
            return (best_plate, max_confidence, winning_vtype)

        return None

    def clear(self):
        self.candidate_buffer.clear()


