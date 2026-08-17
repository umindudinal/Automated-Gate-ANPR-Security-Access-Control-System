import csv
import os
import sqlite3
import cv2
from datetime import datetime
import config
from src.plate_color_detector import PlateColorDetector

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

def calculate_duration(entry_date_str, entry_time_str, exit_date_str, exit_time_str):
    """Calculates human-readable stay duration between entry and exit timestamps."""
    try:
        dt1 = datetime.strptime(f"{entry_date_str} {entry_time_str}", "%Y-%m-%d %H:%M:%S")
        dt2 = datetime.strptime(f"{exit_date_str} {exit_time_str}", "%Y-%m-%d %H:%M:%S")
        diff = dt2 - dt1
        total_seconds = int(diff.total_seconds())
        if total_seconds < 0:
            return "Just now"
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
            
        return " ".join(parts)
    except Exception:
        return "N/A"

def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))

class Database:
    def __init__(self, csv_file=config.CSV_LOG_PATH, db_file=config.SQLITE_DB_PATH):
        self.csv_file = csv_file
        self.db_file = db_file
        self.crops_dir = config.CROPPED_PLATES_DIR
        self.color_detector = PlateColorDetector()
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.csv_file), exist_ok=True)
        os.makedirs(self.crops_dir, exist_ok=True)
        
        self._init_csv()
        self._init_sqlite()
        self._init_mysql()

    def _get_mysql_connection(self, include_db=True):
        """Creates a MySQL connection using parameters from config.py."""
        if not MYSQL_AVAILABLE:
            return None
        
        try:
            kwargs = {
                'host': config.MYSQL_HOST,
                'user': config.MYSQL_USER,
                'password': config.MYSQL_PASSWORD,
                'port': config.MYSQL_PORT
            }
            if include_db:
                kwargs['database'] = config.MYSQL_DB

            return mysql.connector.connect(**kwargs)
        except Exception:
            return None

    def _init_mysql(self):
        """Initializes MySQL database, tables, and performs automatic column migrations."""
        if not MYSQL_AVAILABLE:
            safe_print("[MySQL Warning]: mysql-connector package not installed.")
            return

        try:
            conn = self._get_mysql_connection(include_db=False)
            if conn:
                cursor = conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DB}`")
                conn.commit()
                conn.close()

            conn = self._get_mysql_connection(include_db=True)
            if conn:
                cursor = conn.cursor()
                
                tables = ['vehicle_logs', 'verified_vehicle_logs', 'review_vehicle_logs']
                for tbl in tables:
                    cursor.execute(f'''
                        CREATE TABLE IF NOT EXISTS {tbl} (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            date VARCHAR(20) NOT NULL,
                            time VARCHAR(20) NOT NULL,
                            exit_date VARCHAR(20) DEFAULT '',
                            exit_time VARCHAR(20) DEFAULT '',
                            number_plate VARCHAR(50) NOT NULL,
                            vehicle_type VARCHAR(30) DEFAULT 'Car',
                            status VARCHAR(20) DEFAULT 'INSIDE',
                            duration VARCHAR(30) DEFAULT 'Active',
                            confidence FLOAT NOT NULL,
                            crop_path VARCHAR(255),
                            exit_crop_path VARCHAR(255),
                            plate_color VARCHAR(20) DEFAULT 'YELLOW',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

                    # Auto-migration check for existing legacy tables
                    cursor.execute(f"SHOW COLUMNS FROM `{tbl}`")
                    existing_cols = [col[0] for col in cursor.fetchall()]
                    
                    columns_to_add = [
                        ("exit_date", "VARCHAR(20) DEFAULT ''"),
                        ("exit_time", "VARCHAR(20) DEFAULT ''"),
                        ("status", "VARCHAR(20) DEFAULT 'INSIDE'"),
                        ("duration", "VARCHAR(30) DEFAULT 'Active'"),
                        ("exit_crop_path", "VARCHAR(255) DEFAULT ''"),
                        ("plate_color", "VARCHAR(20) DEFAULT 'YELLOW'")
                    ]
                    for col_name, col_def in columns_to_add:
                        if col_name not in existing_cols:
                            try:
                                cursor.execute(f"ALTER TABLE `{tbl}` ADD COLUMN {col_name} {col_def}")
                            except Exception:
                                pass

                conn.commit()
                conn.close()
                safe_print("[MySQL Success]: Connected to MySQL database & schema verified!")
        except Exception as e:
            safe_print(f"[MySQL Init Warning]: Could not connect to MySQL server: {e}")

    def _init_csv(self):
        """Initializes CSV file with header if not existing."""
        if not os.path.exists(self.csv_file) or os.path.getsize(self.csv_file) == 0:
            with open(self.csv_file, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([
                    'ID', 'Entry Date', 'Entry Time', 'Exit Date', 'Exit Time',
                    'Number Plate', 'Vehicle Type', 'Status', 'Duration',
                    'Confidence Score (%)', 'Entry Crop Path', 'Exit Crop Path', 'Plate Color (Yellow/White)'
                ])

    def _init_sqlite(self):
        """Initializes SQLite database schema and performs automatic column migrations."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            tables = ['vehicle_logs', 'verified_vehicle_logs', 'review_vehicle_logs']
            for tbl in tables:
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {tbl} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        time TEXT NOT NULL,
                        exit_date TEXT DEFAULT '',
                        exit_time TEXT DEFAULT '',
                        number_plate TEXT NOT NULL,
                        vehicle_type TEXT DEFAULT 'Car',
                        status TEXT DEFAULT 'INSIDE',
                        duration TEXT DEFAULT 'Active',
                        confidence REAL NOT NULL,
                        crop_path TEXT DEFAULT '',
                        exit_crop_path TEXT DEFAULT '',
                        plate_color TEXT DEFAULT 'YELLOW'
                    )
                ''')

                cursor.execute(f"PRAGMA table_info({tbl})")
                existing_cols = [info[1] for info in cursor.fetchall()]
                
                columns_to_add = [
                    ("exit_date", "TEXT DEFAULT ''"),
                    ("exit_time", "TEXT DEFAULT ''"),
                    ("status", "TEXT DEFAULT 'INSIDE'"),
                    ("duration", "TEXT DEFAULT 'Active'"),
                    ("exit_crop_path", "TEXT DEFAULT ''"),
                    ("plate_color", "TEXT DEFAULT 'YELLOW'")
                ]
                for col_name, col_def in columns_to_add:
                    if col_name not in existing_cols:
                        try:
                            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_def}")
                        except Exception:
                            pass

            conn.commit()
            conn.close()
        except Exception as e:
            safe_print(f"[DB Error]: Failed to initialize SQLite DB: {e}")

    def save_crop_image(self, crop_image, plate_number, tag="ENTRY"):
        """Saves cropped plate image as an audit artifact."""
        if crop_image is None or crop_image.size == 0:
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_plate = "".join([c if c.isalnum() else "_" for c in plate_number])
        filename = f"{timestamp}_{tag}_{sanitized_plate}.jpg"
        filepath = os.path.join(self.crops_dir, filename)
        
        try:
            cv2.imwrite(filepath, crop_image)
            return filepath
        except Exception as e:
            safe_print(f"[Crop Save Error]: {e}")
            return ""

    def get_active_session(self, number_plate):
        """
        Checks if a vehicle is currently registered as INSIDE the premises.
        Returns active record tuple or None.
        """
        # Try MySQL first
        try:
            conn = self._get_mysql_connection(include_db=True)
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, date, time, number_plate, vehicle_type, status, confidence, crop_path, plate_color
                    FROM vehicle_logs
                    WHERE number_plate = %s AND status = 'INSIDE'
                    ORDER BY id DESC LIMIT 1
                ''', (number_plate,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    return row
        except Exception:
            pass

        # SQLite fallback
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, date, time, number_plate, vehicle_type, status, confidence, crop_path, plate_color
                FROM vehicle_logs
                WHERE number_plate = ? AND status = 'INSIDE'
                ORDER BY id DESC LIMIT 1
            ''', (number_plate,))
            row = cursor.fetchone()
            conn.close()
            return row
        except Exception:
            return None

    def log_vehicle(self, number_plate, vehicle_type="Car", confidence=1.0, crop_image=None, plate_color=None):
        """
        Directional Sri Lankan Gate Logging Engine:
        - Analyzes Number Plate Color (Yellow = Rear/Entry, White = Front/Exit).
        - Yellow Plate -> Register as ENTRY (status = INSIDE).
        - White Plate -> Match to active Yellow entry record & register as EXIT (status = EXITED, duration).
        - Prevents duplicate camera triggers within 15s.
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        conf_pct = round(confidence * 100, 2)
        
        # 1. Analyze License Plate Background Color (Yellow vs White)
        if plate_color is None and crop_image is not None:
            detected_color, dir_label, col_score = self.color_detector.detect_color(crop_image)
            plate_color = detected_color
        elif plate_color is None:
            plate_color = "YELLOW"

        active_session = self.get_active_session(number_plate)

        # ---------------------------------------------------------
        # CASE A: WHITE FRONT PLATE DETECTED -> GATE EXIT (EXITED)
        # ---------------------------------------------------------
        if plate_color == "WHITE":
            exit_crop_path = self.save_crop_image(crop_image, number_plate, tag="EXIT") if crop_image is not None else ""

            if active_session:
                rec_id, entry_date, entry_time, plate, vtype, status, prev_conf, entry_crop, entry_color = active_session
                duration_str = calculate_duration(entry_date, entry_time, date_str, time_str)
                
                # Update existing active session in MySQL
                try:
                    conn = self._get_mysql_connection(include_db=True)
                    if conn:
                        cursor = conn.cursor()
                        for tbl in ['vehicle_logs', 'verified_vehicle_logs', 'review_vehicle_logs']:
                            cursor.execute(f'''
                                UPDATE {tbl}
                                SET exit_date = %s, exit_time = %s, status = 'EXITED', duration = %s, exit_crop_path = %s
                                WHERE id = %s OR (number_plate = %s AND status = 'INSIDE')
                            ''', (date_str, time_str, duration_str, exit_crop_path, rec_id, number_plate))
                        conn.commit()
                        conn.close()
                except Exception as e:
                    safe_print(f"[MySQL Exit Update Error]: {e}")

                # Update existing active session in SQLite
                try:
                    conn = sqlite3.connect(self.db_file)
                    cursor = conn.cursor()
                    for tbl in ['vehicle_logs', 'verified_vehicle_logs', 'review_vehicle_logs']:
                        cursor.execute(f'''
                            UPDATE {tbl}
                            SET exit_date = ?, exit_time = ?, status = 'EXITED', duration = ?, exit_crop_path = ?
                            WHERE id = ? OR (number_plate = ? AND status = 'INSIDE')
                        ''', (date_str, time_str, duration_str, exit_crop_path, rec_id, number_plate))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    safe_print(f"[SQLite Exit Update Error]: {e}")

                # CSV Logging for Exit Event
                try:
                    with open(self.csv_file, mode='a', newline='', encoding='utf-8') as file:
                        writer = csv.writer(file)
                        writer.writerow([
                            rec_id, entry_date, entry_time, date_str, time_str,
                            number_plate, vehicle_type, 'EXITED', duration_str,
                            f"{conf_pct}%", entry_crop, exit_crop_path, 'WHITE'
                        ])
                except Exception as e:
                    safe_print(f"[CSV Error]: {e}")

                safe_print(f"[GATE EXIT (⚪ White Front Plate)]: {date_str} {time_str} | Plate: {number_plate} | Type: {vehicle_type} | Duration: {duration_str}")
                return ("EXIT", exit_crop_path, "WHITE")

            else:
                # Standalone Exit (No prior Yellow Entry recorded)
                is_verified = conf_pct >= 90.0
                segmented_table = "verified_vehicle_logs" if is_verified else "review_vehicle_logs"

                try:
                    conn = self._get_mysql_connection(include_db=True)
                    if conn:
                        cursor = conn.cursor()
                        query = '''
                            INSERT INTO vehicle_logs (date, time, exit_date, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, plate_color)
                            VALUES (%s, '-', %s, %s, %s, %s, 'EXITED', 'Exit Only', %s, '', %s, 'WHITE')
                        '''
                        cursor.execute(query, (date_str, date_str, time_str, number_plate, vehicle_type, conf_pct, exit_crop_path))
                        
                        query_seg = f'''
                            INSERT INTO {segmented_table} (date, time, exit_date, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, plate_color)
                            VALUES (%s, '-', %s, %s, %s, %s, 'EXITED', 'Exit Only', %s, '', %s, 'WHITE')
                        '''
                        cursor.execute(query_seg, (date_str, date_str, time_str, number_plate, vehicle_type, conf_pct, exit_crop_path))

                        conn.commit()
                        conn.close()
                except Exception as e:
                    safe_print(f"[MySQL Standalone Exit Log Error]: {e}")

                try:
                    conn = sqlite3.connect(self.db_file)
                    cursor = conn.cursor()
                    query_sqlite = '''
                        INSERT INTO vehicle_logs (date, time, exit_date, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, plate_color)
                        VALUES (?, '-', ?, ?, ?, ?, 'EXITED', 'Exit Only', ?, '', ?, 'WHITE')
                    '''
                    cursor.execute(query_sqlite, (date_str, date_str, time_str, number_plate, vehicle_type, conf_pct, exit_crop_path))
                    
                    query_seg_sqlite = f'''
                        INSERT INTO {segmented_table} (date, time, exit_date, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, plate_color)
                        VALUES (?, '-', ?, ?, ?, ?, 'EXITED', 'Exit Only', ?, '', ?, 'WHITE')
                    '''
                    cursor.execute(query_seg_sqlite, (date_str, date_str, time_str, number_plate, vehicle_type, conf_pct, exit_crop_path))

                    conn.commit()
                    conn.close()
                except Exception as e:
                    safe_print(f"[SQLite Standalone Exit Log Error]: {e}")

                try:
                    with open(self.csv_file, mode='a', newline='', encoding='utf-8') as file:
                        writer = csv.writer(file)
                        writer.writerow([
                            'NEW', date_str, '-', date_str, time_str,
                            number_plate, vehicle_type, 'EXITED', 'Exit Only',
                            f"{conf_pct}%", '', exit_crop_path, 'WHITE'
                        ])
                except Exception as e:
                    safe_print(f"[CSV Error]: {e}")

                safe_print(f"[GATE EXIT (⚪ Standalone White Front Plate)]: {date_str} {time_str} | Plate: {number_plate} | Status: EXITED")
                return ("EXIT", exit_crop_path, "WHITE")

        # ---------------------------------------------------------
        # CASE B: YELLOW REAR PLATE DETECTED -> GATE ENTRY (INSIDE)
        # ---------------------------------------------------------
        if active_session:
            rec_id, entry_date, entry_time, plate, vtype, status, prev_conf, entry_crop, entry_color = active_session
            try:
                entry_dt = datetime.strptime(f"{entry_date} {entry_time}", "%Y-%m-%d %H:%M:%S")
                elapsed_sec = (now - entry_dt).total_seconds()
            except Exception:
                elapsed_sec = 999.0

            # Ignore duplicate Yellow entry camera triggers within 15s of entering
            if elapsed_sec < 15.0:
                safe_print(f"[Duplicate Trigger Ignored]: {number_plate} (Entered {int(elapsed_sec)}s ago)")
                return ("IGNORED", entry_crop, "YELLOW")

        crop_path = self.save_crop_image(crop_image, number_plate, tag="ENTRY") if crop_image is not None else ""
        is_verified = conf_pct >= 90.0
        segmented_table = "verified_vehicle_logs" if is_verified else "review_vehicle_logs"
        category_tag = "Verified (>=90%)" if is_verified else "Review (<90%)"

        # 1. Insert into MySQL
        mysql_logged = False
        try:
            conn = self._get_mysql_connection(include_db=True)
            if conn:
                cursor = conn.cursor()
                query = '''
                    INSERT INTO vehicle_logs (date, time, exit_date, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, plate_color)
                    VALUES (%s, %s, '', '', %s, %s, 'INSIDE', 'Active', %s, %s, '', 'YELLOW')
                '''
                cursor.execute(query, (date_str, time_str, number_plate, vehicle_type, conf_pct, crop_path))
                
                query_seg = f'''
                    INSERT INTO {segmented_table} (date, time, exit_date, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, plate_color)
                    VALUES (%s, %s, '', '', %s, %s, 'INSIDE', 'Active', %s, %s, '', 'YELLOW')
                '''
                cursor.execute(query_seg, (date_str, time_str, number_plate, vehicle_type, conf_pct, crop_path))

                conn.commit()
                conn.close()
                mysql_logged = True
        except Exception as e:
            safe_print(f"[MySQL Entry Log Error]: {e}")

        # 2. Insert into SQLite
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            query_sqlite = '''
                INSERT INTO vehicle_logs (date, time, exit_date, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, plate_color)
                VALUES (?, ?, '', '', ?, ?, 'INSIDE', 'Active', ?, ?, '', 'YELLOW')
            '''
            cursor.execute(query_sqlite, (date_str, time_str, number_plate, vehicle_type, conf_pct, crop_path))
            
            query_seg_sqlite = f'''
                INSERT INTO {segmented_table} (date, time, exit_date, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, plate_color)
                VALUES (?, ?, '', '', ?, ?, 'INSIDE', 'Active', ?, ?, '', 'YELLOW')
            '''
            cursor.execute(query_seg_sqlite, (date_str, time_str, number_plate, vehicle_type, conf_pct, crop_path))

            conn.commit()
            conn.close()
        except Exception as e:
            safe_print(f"[SQLite Entry Log Error]: {e}")

        # 3. CSV Log
        try:
            with open(self.csv_file, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([
                    'NEW', date_str, time_str, '', '',
                    number_plate, vehicle_type, 'INSIDE', 'Active',
                    f"{conf_pct}%", crop_path, '', 'YELLOW'
                ])
        except Exception as e:
            safe_print(f"[CSV Error]: {e}")

        status_tag = f"MySQL & Local [{category_tag}]" if mysql_logged else f"Local File [{category_tag}]"
        safe_print(f"[GATE ENTRY (🟡 Yellow Rear Plate - {status_tag})]: {date_str} {time_str} | Plate: {number_plate} | Type: {vehicle_type} | Status: INSIDE")
        return ("ENTRY", crop_path, "YELLOW")

    def get_logs_from_table(self, table_name="vehicle_logs"):
        """Retrieves logged vehicle entries with full Gate Access fields including plate_color."""
        sql = f'''
            SELECT id, date, time, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, exit_date, plate_color
            FROM {table_name}
            ORDER BY id DESC
        '''
        # Try MySQL first
        try:
            conn = self._get_mysql_connection(include_db=True)
            if conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                conn.close()
                return rows
        except Exception:
            pass

        # Fallback SQLite
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            safe_print(f"[SQLite Fetch Error ({table_name})]: {e}")
            return []

    def get_all_logs(self):
        """Retrieves all master vehicle gate logs."""
        return self.get_logs_from_table("vehicle_logs")

    def get_inside_logs(self):
        """Retrieves vehicles currently inside institution premises."""
        sql = '''
            SELECT id, date, time, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, exit_date, plate_color
            FROM vehicle_logs
            WHERE status = 'INSIDE'
            ORDER BY id DESC
        '''
        try:
            conn = self._get_mysql_connection(include_db=True)
            if conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                conn.close()
                return rows
        except Exception:
            pass

        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception:
            return []

    def get_exited_logs(self):
        """Retrieves vehicles that have completed visit and exited."""
        sql = '''
            SELECT id, date, time, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, exit_date, plate_color
            FROM vehicle_logs
            WHERE status = 'EXITED'
            ORDER BY id DESC
        '''
        try:
            conn = self._get_mysql_connection(include_db=True)
            if conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                conn.close()
                return rows
        except Exception:
            pass

        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception:
            return []

    def get_verified_logs(self):
        """Retrieves verified vehicle entries (Confidence >= 90%)."""
        return self.get_logs_from_table("verified_vehicle_logs")

    def get_review_logs(self):
        """Retrieves entries requiring review (Confidence < 90%)."""
        return self.get_logs_from_table("review_vehicle_logs")

    def clear_all_logs(self):
        """Clears all vehicle log records from MySQL, SQLite, CSV, and deletes crop images."""
        tables = ['vehicle_logs', 'verified_vehicle_logs', 'review_vehicle_logs']
        
        # 1. Clear MySQL tables
        try:
            conn = self._get_mysql_connection(include_db=True)
            if conn:
                cursor = conn.cursor()
                for tbl in tables:
                    cursor.execute(f"TRUNCATE TABLE `{tbl}`")
                conn.commit()
                conn.close()
                safe_print("[MySQL Clear]: Truncated all log tables.")
        except Exception as e:
            safe_print(f"[MySQL Clear Error]: {e}")

        # 2. Clear SQLite tables
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            for tbl in tables:
                cursor.execute(f"DELETE FROM `{tbl}`")
            conn.commit()
            conn.close()
            safe_print("[SQLite Clear]: Cleared all log tables.")
        except Exception as e:
            safe_print(f"[SQLite Clear Error]: {e}")

        # 3. Reset CSV file header
        try:
            with open(self.csv_file, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([
                    'ID', 'Entry Date', 'Entry Time', 'Exit Date', 'Exit Time',
                    'Number Plate', 'Vehicle Type', 'Status', 'Duration',
                    'Confidence Score (%)', 'Entry Crop Path', 'Exit Crop Path', 'Plate Color (Yellow/White)'
                ])
        except Exception as e:
            safe_print(f"[CSV Clear Error]: {e}")

        # 4. Delete cropped images
        try:
            if os.path.exists(self.crops_dir):
                for filename in os.listdir(self.crops_dir):
                    file_path = os.path.join(self.crops_dir, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                safe_print("[Crops Clear]: Purged cropped images folder.")
        except Exception as e:
            safe_print(f"[Crops Clear Error]: {e}")