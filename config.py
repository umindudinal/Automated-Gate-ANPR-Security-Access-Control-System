import os

# Base Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
INPUT_VIDEOS_DIR = os.path.join(DATA_DIR, 'input_videos')
INPUT_IMAGES_DIR = os.path.join(DATA_DIR, 'input_images')

MODELS_DIR = os.path.join(BASE_DIR, 'models')
YOLO_MODEL_PATH = os.path.join(MODELS_DIR, 'license_plate_detector.pt')
FALLBACK_YOLO_MODEL = os.path.join(BASE_DIR, 'yolov8n.pt')

OUTPUTS_DIR = os.path.join(BASE_DIR, 'outputs')
CROPPED_PLATES_DIR = os.path.join(OUTPUTS_DIR, 'cropped_plates')
CSV_LOG_PATH = os.path.join(OUTPUTS_DIR, 'vehicle_logs.csv')
SQLITE_DB_PATH = os.path.join(OUTPUTS_DIR, 'campus_anpr.db')

# MySQL Database Configuration
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '0318')
MYSQL_DB = os.getenv('MYSQL_DB', 'campus_anpr_db')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))


# Ensure directories exist
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(CROPPED_PLATES_DIR, exist_ok=True)

# Performance & OCR Settings
OCR_CONFIDENCE_THRESHOLD = 0.50  # Minimum confidence (50%) to accept OCR text
FRAME_SKIP_RATE = 3               # Process every 3rd frame for speed & responsiveness
VOTING_WINDOW_FRAMES = 8          # Number of detections collected per vehicle before locking
PLATE_COOLDOWN_SECONDS = 45       # Seconds before same or similar vehicle can be logged again

# Sri Lankan Vehicle Registration Formats
PROVINCE_CODES = ['WP', 'NW', 'CP', 'SP', 'UP', 'SG', 'NC', 'EP', 'NP']
DEFAULT_PROVINCE = 'WP'  # Default province fallback when small font province is missed by OCR

# Valid Sri Lankan Plate Regex Patterns
SRI_LANKAN_MODERN_REGEX = r'^(?:(WP|NW|CP|SP|UP|SG|NC|EP|NP)\s+)?([A-Z]{2,3})\s*[-–\s]?\s*(\d{4})$'
SRI_LANKAN_VINTAGE_REGEX = r'^(?:(WP|NW|CP|SP|UP|SG|NC|EP|NP)\s+)?([0-9]{1,3}|[A-Z]{1,2})\s*[-–\s]?\s*(\d{4})$'
