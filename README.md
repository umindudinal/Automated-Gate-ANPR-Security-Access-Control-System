<div align="center">

# 🚘 Automated Gate ANPR Security & Access Control System

**AI-powered vehicle gate automation using YOLOv8 detection and EasyOCR recognition, purpose-built for Sri Lankan license plate standards.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00FFFF?logo=yolo&logoColor=black)](https://github.com/ultralytics/ultralytics)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![EasyOCR](https://img.shields.io/badge/OCR-EasyOCR-orange)](https://github.com/JaidedAI/EasyOCR)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 📖 Overview

The **Automated Gate ANPR Security & Access Control System** is an end-to-end computer vision pipeline that detects vehicles and license plates in real time, reads plate numbers with a multi-pipeline OCR engine tuned for **Sri Lankan number plate formats**, and automatically logs gate **entry/exit** events to a database with a live dashboard.

The system distinguishes between a vehicle's **yellow rear plate (Entry)** and **white front plate (Exit)** to automatically determine gate direction — no manual barrier operation or separate entry/exit cameras required.

Built for institutional and campus gate security, it can just as easily be adapted for corporate parks, gated communities, and parking facilities.

---

## ✨ Key Features

- 🔍 **Real-time Vehicle & Plate Detection** — YOLOv8 detects license plates while a second YOLOv8 (COCO) model classifies the parent vehicle (Car, Van, Bike, Bus, Truck) and links each plate to its vehicle.
- 🔤 **Multi-Pipeline OCR Engine** — Each plate crop is processed through three preprocessing pipelines (CLAHE + bilateral filter, adaptive thresholding, Otsu thresholding) and read via EasyOCR, keeping the highest-confidence result.
- 🇱🇰 **Sri Lankan Plate Intelligence** — A dedicated correction engine fixes common OCR misreads (`O↔0`, `S↔5`, `I↔1`, etc.), validates against modern (`WP CAB - 6036`) and vintage (`64 - 6036`) plate formats, and auto-corrects known province-code errors.
- 🎯 **Smart Voting & Cooldown Buffer** — Detections are pooled across a sliding frame window and grouped by trailing digits, so the highest-confidence, most-voted reading wins — filtering out noisy single-frame misreads and duplicate logs for the same vehicle.
- 🟡⚪ **Automatic Entry/Exit Detection** — HSV color analysis on the plate crop distinguishes Sri Lanka's yellow rear plates from white front plates to automatically classify the event as **ENTRY** or **EXIT**.
- 🗄️ **Triple-Redundant Logging** — Every event is written to **MySQL** (primary), **SQLite** (local fallback), and a **CSV** audit log simultaneously, with automatic schema migration for new columns.
- ⏱️ **Live Session Tracking** — Tracks vehicles currently inside the premises and calculates human-readable stay duration (e.g., `2h 15m 30s`) on exit.
- 🖥️ **Two Ready-to-Use Interfaces**:
  - A **desktop GUI** (`gui_app.py`) built with CustomTkinter for live monitoring, manual review, and register management.
  - A **web dashboard** (`ui/app.py`) built with Streamlit for browsing logs, active sessions, and audit trails from anywhere.
- 📸 **Audit Trail Snapshots** — Every logged plate is saved as a timestamped cropped image for manual verification.

---

## 🏗️ Architecture

```
Video Feed / Camera
        │
        ▼
┌─────────────────────┐      ┌──────────────────────┐
│  LicensePlateDetector│─────▶│   Vehicle Type Match  │
│  (YOLOv8, custom)    │      │   (COCO YOLOv8n)      │
└─────────────────────┘      └──────────────────────┘
        │  plate crop
        ▼
┌─────────────────────┐
│     OCRReader         │  3× preprocessing pipelines → EasyOCR
│  + Plate Correction   │  → Sri Lankan format validation
└─────────────────────┘
        │  candidate plate + confidence
        ▼
┌─────────────────────┐
│    PlateBuffer         │  Sliding-window voting + smart cooldown
└─────────────────────┘
        │  winning plate
        ▼
┌─────────────────────┐      ┌──────────────────────┐
│ PlateColorDetector     │─────▶│  ENTRY (Yellow) /      │
│ (HSV yellow/white)     │      │  EXIT (White)          │
└─────────────────────┘      └──────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│   Database  →  MySQL + SQLite + CSV (synced) │
└─────────────────────────────────────────────┘
        │
        ▼
   GUI (Tkinter)  /  Web Dashboard (Streamlit)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Object Detection | [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) |
| OCR Engine | [EasyOCR](https://github.com/JaidedAI/EasyOCR) |
| Image Processing | [OpenCV](https://opencv.org/) |
| Desktop GUI | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) |
| Web Dashboard | [Streamlit](https://streamlit.io/) |
| Database | MySQL + SQLite (dual-write with auto-migration) |
| Data Handling | Pandas, NumPy |
| Language | Python 3.9+ |

---

## 📂 Project Structure

```
Automated-Gate-ANPR-Security-Access-Control-System/
├── main.py                    # CLI entry point — video processing pipeline
├── gui_app.py                 # Desktop GUI (CustomTkinter)
├── config.py                  # Central configuration (paths, thresholds, plate regex)
├── download_model.py          # Downloads the pretrained license plate YOLOv8 model
├── requirements.txt           # Python dependencies
├── src/
│   ├── detector.py            # YOLOv8 plate detection + vehicle type classification
│   ├── ocr_reader.py          # Multi-pipeline OCR + Sri Lankan plate correction
│   ├── plate_buffer.py        # Sliding-window voting & smart cooldown logic
│   ├── plate_color_detector.py# Yellow/White plate HSV classification (Entry/Exit)
│   └── database.py            # MySQL / SQLite / CSV triple-write logging layer
├── ui/
│   └── app.py                 # Streamlit web dashboard
├── data/
│   ├── input_videos/          # Place source gate footage here (test_video.mp4)
│   └── input_images/          # Sample/test images
└── outputs/                   # Auto-generated logs, cropped plates, SQLite DB
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.9 or higher
- MySQL Server (optional — the system automatically falls back to SQLite if unavailable)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/umindudinal/Automated-Gate-ANPR-Security-Access-Control-System.git
cd Automated-Gate-ANPR-Security-Access-Control-System

# 2. Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download the pretrained license plate detection model
python download_model.py
```

### Configuration

Set your MySQL credentials via environment variables (optional — defaults to `localhost`/`root`):

```bash
export MYSQL_HOST=localhost
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DB=campus_anpr_db
```

If MySQL is not configured or unreachable, the system automatically logs to **SQLite** and **CSV** without any changes required.

---

## 🚀 Usage

### 1. Command-Line Video Processing
Place a video file named `test_video.mp4` inside `data/input_videos/`, then run:

```bash
python main.py
```
Press **`q`** to stop the live feed window at any time.

### 2. Desktop GUI Application
```bash
python gui_app.py
```
Provides live monitoring, manual review of low-confidence reads, and a full vehicle register — all in a single desktop window.

### 3. Web Dashboard
```bash
streamlit run ui/app.py
```
Browse entry/exit logs, currently active (inside) vehicles, and verification queues from any browser.

---

## 🇱🇰 Sri Lankan Plate Format Support

The OCR correction engine is built specifically around Sri Lanka's registration standards:

| Format | Example | Description |
|---|---|---|
| Modern | `WP CAB - 6036` | Province code + 2–3 letter series + 4 digits |
| Vintage | `64 - 6036` | Legacy numeric/short-letter series + 4 digits |

Supported province codes: `WP, NW, CP, SP, UP, SG, NC, EP, NP`

Plate color also drives the entry/exit logic:
- 🟡 **Yellow (rear plate)** → Logged as **Gate ENTRY**
- ⚪ **White (front plate)** → Logged as **Gate EXIT**

---

## 🗃️ Database Schema (simplified)

| Column | Description |
|---|---|
| `number_plate` | Validated, formatted plate string |
| `vehicle_type` | Car / Van / Bike / Bus / Truck |
| `status` | `INSIDE` or `EXITED` |
| `duration` | Auto-calculated stay duration on exit |
| `confidence` | OCR confidence score |
| `crop_path` / `exit_crop_path` | Saved audit-trail plate images |
| `plate_color` | `YELLOW` (entry) or `WHITE` (exit) |

Records are written simultaneously to `vehicle_logs`, `verified_vehicle_logs` (confidence ≥ 90%), and `review_vehicle_logs` (confidence < 90%) for easy manual auditing.

---

## 🗺️ Roadmap

- [ ] Live RTSP/IP camera stream support
- [ ] Automated barrier/relay hardware integration
- [ ] REST API layer for third-party integration
- [ ] Multi-gate / multi-camera support
- [ ] Mobile companion app for security personnel

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome. Feel free to check the [issues page](https://github.com/umindudinal/Automated-Gate-ANPR-Security-Access-Control-System/issues) or open a pull request.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Umindu Dinal**
IT Undergraduate, Institute of Technology, University of Moratuwa (ITUM)

- GitHub: [@umindudinal](https://github.com/umindudinal)

<div align="center">

⭐ If you find this project useful, consider giving it a star!

</div>

