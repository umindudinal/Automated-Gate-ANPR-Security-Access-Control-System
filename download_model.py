import urllib.request
import os

# අංක තහඩු සඳහා පුහුණු කළ YOLOv8 මාදිලියේ සබැඳිය (HuggingFace ගබඩාවෙන්)
url = "https://huggingface.co/keremberke/yolov8n-license-plate/resolve/main/best.pt"
output_path = "models/license_plate_detector.pt"

print("AI Model එක Download වීම ආරම්භ විය. මෙයට මිනිත්තු කිහිපයක් ගතවනු ඇත...")
print("කරුණාකර රැඳී සිටින්න...")

try:
    urllib.request.urlretrieve(url, output_path)
    print(f"\nසාර්ථකයි! Model එක '{output_path}' ලෙස සුරක්ෂිතව ගබඩා විය.")
except Exception as e:
    print(f"\nදෝෂයක් මතු විය: {e}")