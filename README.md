# 🚘 Automated Gate ANPR Security & Access Control System

An enterprise-grade **Automatic Number Plate Recognition (ANPR)** system built for gate-level vehicle access control. The system uses **YOLOv8** for real-time vehicle and license plate detection, **EasyOCR** with a custom Sri Lankan plate-correction engine for text extraction, and an HSV-based plate-color classifier to automatically distinguish **Entry (Yellow rear plate)** from **Exit (White front plate)** events — logging every vehicle movement to a dual-backend database (MySQL with automatic SQLite fallback) plus CSV, complete with cropped plate image audit trails.

---

## ✨ Key Features

- **Real-time vehicle & plate detection** — Dual YOLOv8 pipeline: one model detects and classifies vehicles (Car, Van, Bike, Bus, Truck), the other detects license plates and maps each plate to its parent vehicle.
- **Sri Lankan plate-aware OCR engine** — EasyOCR runs across 3 parallel image-preprocessing pipelines (CLAHE, adaptive threshold, Otsu threshold) and the highest-confidence result is selected.
- **Custom character-correction logic** — Domain-specific rules fix common OCR misreads (e.g. `O↔0`, `S↔5`, `I↔1`), validate against modern and vintage Sri Lankan plate formats, and auto-correct corrupted province codes (`WP`, `NW`, `CP`, `SP`, `UP`, `SG`, `NC`, `EP`, `NP`).
- **Yellow/White plate color classification** — HSV-based detector distinguishes the rear (yellow) plate from the front (white) plate to automatically tag a detection as a Gate **ENTRY** or **EXIT** event.
- **Smart voting & cooldown buffer** — Groups detections per vehicle over a sliding frame window, picks the highest-confidence reading, and prevents duplicate logging of the same vehicle within a configurable cooldown period.
- **Dual-database persistence** — Logs are written to **MySQL** (primary) with automatic fallback to **SQLite**, alongside a plain **CSV** log and saved plate-crop images for audit purposes.
- **Two front-ends**:
  - A **Streamlit web dashboard** (`ui/app.py`) for browsing master, inside, exited, verified, and review logs.
  - A **desktop GUI** (`gui_app.py`) built with CustomTkinter for live monitoring with an on-screen video feed.
- **CLI mode** (`main.py`) — Lightweight OpenCV-window runner for quick testing against a sample video.

---

## 🏗️ System Architecture

```
Video / Camera Feed
        │
        ▼
┌────────────────────────┐      ┌────────────────────────┐
│  LicensePlateDetector   │ ---> │ Vehicle Classification  │  (YOLOv8 - COCO)
│   (src/detector.py)     │      │ Car / Van / Bike /       │
└────────────────────────┘      │ Bus / Truck              │
        │                       └────────────────────────┘
        ▼
┌────────────────────────┐
│      OCRReader           │  Multi-pipeline preprocessing + EasyOCR +
│  (src/ocr_reader.py)     │  Sri Lankan plate validation/formatting
└────────────────────────┘
        │
        ▼
┌────────────────────────┐
│   PlateColorDetector     │  Yellow (rear/entry) vs White (front/exit)
│ (src/plate_color_        │
│     detector.py)         │
└────────────────────────┘
        │
        ▼
┌────────────────────────┐
│      PlateBuffer          │  Sliding-window voting + smart cooldown
│  (src/plate_buffer.py)    │  (de-duplication across frames)
└────────────────────────┘
        │
        ▼
┌────────────────────────┐
│       Database              │  MySQL (primary) → SQLite (fallback) → CSV
│   (src/database.py)         │  + cropped plate image audit trail
└────────────────────────┘
        │
        ▼
  Streamlit Dashboard  /  CustomTkinter Desktop GUI
```

---

## 📁 Project Structure

```
Automated-Gate-ANPR-Security-Access-Control-System/
├── main.py                    # CLI entry point (OpenCV live-window runner)
├── gui_app.py                 # Desktop GUI application (CustomTkinter)
├── config.py                  # Central configuration (paths, DB, thresholds, plate regex)
├── download_model.py          # Downloads the pretrained YOLOv8 plate-detector weights
├── requirements.txt           # Python dependencies
├── src/
│   ├── detector.py            # Vehicle + license plate detection (YOLOv8)
│   ├── ocr_reader.py          # OCR preprocessing, reading & plate validation/formatting
│   ├── plate_buffer.py        # Sliding-window voting & cooldown de-duplication
│   ├── plate_color_detector.py# Yellow/White plate color classification
│   └── database.py            # MySQL / SQLite / CSV persistence layer
├── ui/
│   └── app.py                 # Streamlit web dashboard
├── data/
│   ├── input_videos/          # Place test video(s) here (e.g. test_video.mp4)
│   └── input_images/          # Place test image(s) here
└── outputs/                   # Auto-generated: cropped plates, logs, SQLite DB
```

---

## ⚙️ Tech Stack

| Layer                 | Technology                                   |
|------------------------|-----------------------------------------------|
| Object Detection       | YOLOv8 (`ultralytics`)                        |
| OCR                     | EasyOCR                                       |
| Computer Vision         | OpenCV                                        |
| Web Dashboard           | Streamlit                                     |
| Desktop GUI             | CustomTkinter (Tkinter)                       |
| Database                 | MySQL (`mysql-connector-python`) + SQLite (fallback) |
| Data Handling             | Pandas, NumPy, Pillow                       |
| Language                  | Python 3                                     |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- MySQL Server (optional — the system automatically falls back to SQLite if MySQL is unavailable)

### 1. Clone the repository

```bash
git clone https://github.com/umindudinal/Automated-Gate-ANPR-Security-Access-Control-System.git
cd Automated-Gate-ANPR-Security-Access-Control-System
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Download the license plate detection model

```bash
python download_model.py
```

This downloads the pretrained YOLOv8 license-plate weights into `models/license_plate_detector.pt`. If this file is missing at runtime, the system automatically falls back to the base `yolov8n.pt` model.

### 4. Configure the database (optional)

By default, the app connects to a local MySQL instance using the settings in `config.py`. Override these via environment variables instead of editing the file directly:

```bash
export MYSQL_HOST=localhost
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DB=campus_anpr_db
export MYSQL_PORT=3306
```

> If MySQL is not reachable, the system automatically logs to a local **SQLite** database at `outputs/campus_anpr.db` and a CSV file at `outputs/vehicle_logs.csv`, so no database setup is strictly required to try the system out.

### 5. Add a test video

Place a video file named `test_video.mp4` inside `data/input_videos/` (or point the GUI's file picker to any video of your choice).

---

## ▶️ Usage

### Option A — Command-line runner

```bash
python main.py
```

Opens an OpenCV window with a live annotated feed (bounding boxes, plate labels, and a running gate-log overlay). Press `q` to stop.

### Option B — Desktop GUI

```bash
python gui_app.py
```

Launches the full CustomTkinter desktop application with live monitoring, master/inside/exited log views, and image previews.

### Option C — Streamlit web dashboard

```bash
streamlit run ui/app.py
```

Opens a browser-based dashboard for reviewing Master Register, Inside/Exited vehicles, and Verified/Review logs.

---

## 🔍 How Plate Recognition Works

1. **Detection** — Each frame is run through a YOLOv8 vehicle-classification model and a YOLOv8 license-plate detector; plates are spatially matched to their parent vehicle.
2. **Preprocessing** — Each cropped plate image is passed through 3 preprocessing pipelines (CLAHE + bilateral filter, adaptive threshold, Otsu threshold) to maximize OCR accuracy under varying lighting.
3. **OCR & correction** — EasyOCR reads text from all 3 pipelines; a Sri Lanka-specific character-correction engine fixes common misreads and formats the result into the standard `PROVINCE LETTERS - DIGITS` layout (e.g. `WP CAB - 6036`).
4. **Color classification** — The plate crop is analyzed in HSV space to determine whether it's the **yellow rear plate** (→ Entry) or **white front plate** (→ Exit).
5. **Voting & cooldown** — Detections are grouped by trailing digits across a sliding window of frames; the highest-confidence candidate "wins" and is locked in, while a smart cooldown (exact match, digit match, or >70% string similarity) prevents the same vehicle being logged twice within a short window.
6. **Persistence** — The final result is written to MySQL/SQLite and CSV, along with a saved crop image for audit purposes.

---

## 🇱🇰 Sri Lankan Plate Format Support

The system recognizes both modern and vintage Sri Lankan plate formats:

- **Modern:** `[Province] [2–3 Letters] [4 Digits]` → e.g. `WP CAB - 6036`
- **Vintage:** `[Province] [1–3 Digits/Letters] [4 Digits]` → e.g. `64 - 6036`

Supported province codes: `WP`, `NW`, `CP`, `SP`, `UP`, `SG`, `NC`, `EP`, `NP`.

---

## 🛠️ Configuration

Key tunables live in `config.py`:

| Setting | Description | Default |
|---|---|---|
| `OCR_CONFIDENCE_THRESHOLD` | Minimum OCR confidence to accept a reading | `0.50` |
| `FRAME_SKIP_RATE` | Process every Nth frame for performance | `3` |
| `VOTING_WINDOW_FRAMES` | Detections collected per vehicle before locking a result | `8` |
| `PLATE_COOLDOWN_SECONDS` | Cooldown before the same vehicle can be logged again | `45` |

---

## 📄 License

No license file is currently included in this repository. Consider adding one (e.g. MIT) if you intend for others to reuse this code.

---

## 👤 Author

**Umindu Dinal** — [@umindudinal](https://github.com/umindudinal)
