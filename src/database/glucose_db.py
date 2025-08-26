import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class GlucoseReading:
    timestamp: datetime
    value: float
    trend: Optional[str] = None
    unit: str = "mg/dL"
    id: Optional[int] = None

@dataclass
class InsulinEntry:
    timestamp: datetime
    units: float
    insulin_type: str  # 'rapid', 'long_acting', 'intermediate'
    duration_minutes: int = 180  # Default 3 hours for rapid-acting
    notes: Optional[str] = None
    id: Optional[int] = None

@dataclass
class CarbEntry:
    timestamp: datetime
    grams: float
    carb_type: Optional[str] = None  # 'fast', 'slow', 'mixed'
    absorption_minutes: int = 120  # Default 2 hours
    notes: Optional[str] = None
    id: Optional[int] = None

@dataclass  
class IOBOverride:
    timestamp: datetime
    iob_value: float
    source: str = 'manual'  # 'manual', 'omnipod', 'pump'
    notes: Optional[str] = None
    id: Optional[int] = None

@dataclass
class GlucoseNote:
    timestamp: datetime
    note_text: str
    note_type: str = 'observation'  # 'observation', 'trend', 'recommendation-note'
    glucose_value: Optional[float] = None
    context_data: Optional[str] = None  # JSON string for additional context (IOB, COB, etc.)
    id: Optional[int] = None

class GlucoseDatabase:
    def __init__(self, db_path: str = "glucose_monitor.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS glucose_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    value REAL NOT NULL,
                    trend TEXT,
                    unit TEXT DEFAULT 'mg/dL',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    recommendation_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    glucose_value REAL NOT NULL,
                    parameters TEXT,
                    sent_to_telegram INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS insulin_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    units REAL NOT NULL,
                    insulin_type TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 180,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS carb_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    grams REAL NOT NULL,
                    carb_type TEXT,
                    absorption_minutes INTEGER DEFAULT 120,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS iob_overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    iob_value REAL NOT NULL,
                    source TEXT DEFAULT 'manual',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS glucose_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    note_text TEXT NOT NULL,
                    note_type TEXT DEFAULT 'observation',
                    glucose_value REAL,
                    context_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_glucose_timestamp 
                ON glucose_readings(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_insulin_timestamp 
                ON insulin_entries(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_carb_timestamp 
                ON carb_entries(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_iob_override_timestamp 
                ON iob_overrides(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_glucose_notes_timestamp 
                ON glucose_notes(timestamp)
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def insert_reading(self, reading: GlucoseReading) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if reading already exists with same timestamp and value
            cursor.execute('''
                SELECT id FROM glucose_readings 
                WHERE timestamp = ? AND value = ?
            ''', (reading.timestamp.isoformat(), reading.value))
            
            existing = cursor.fetchone()
            if existing:
                logger.debug(f"Reading already exists: {reading.value} {reading.unit} at {reading.timestamp}")
                return existing[0]
            
            cursor.execute('''
                INSERT INTO glucose_readings (timestamp, value, trend, unit)
                VALUES (?, ?, ?, ?)
            ''', (
                reading.timestamp.isoformat(),
                reading.value,
                reading.trend,
                reading.unit
            ))
            conn.commit()
            reading_id = cursor.lastrowid
            logger.info(f"Inserted glucose reading: {reading.value} {reading.unit} at {reading.timestamp}")
            return reading_id
    
    def get_latest_readings(self, count: int = 20) -> List[GlucoseReading]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, value, trend, unit
                FROM glucose_readings
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (count,))
            
            readings = []
            for row in cursor.fetchall():
                reading = GlucoseReading(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    value=row[2],
                    trend=row[3],
                    unit=row[4]
                )
                readings.append(reading)
            
            return readings
    
    def get_readings_since(self, since: datetime) -> List[GlucoseReading]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, value, trend, unit
                FROM glucose_readings
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            ''', (since.isoformat(),))
            
            readings = []
            for row in cursor.fetchall():
                reading = GlucoseReading(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    value=row[2],
                    trend=row[3],
                    unit=row[4]
                )
                readings.append(reading)
            
            return readings
    
    def insert_recommendation(self, timestamp: datetime, rec_type: str, 
                            message: str, glucose_value: float, 
                            parameters: str = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO recommendations 
                (timestamp, recommendation_type, message, glucose_value, parameters)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                timestamp.isoformat(),
                rec_type,
                message,
                glucose_value,
                parameters
            ))
            conn.commit()
            rec_id = cursor.lastrowid
            logger.info(f"Inserted recommendation: {rec_type} - {message}")
            return rec_id
    
    def mark_recommendation_sent(self, rec_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE recommendations 
                SET sent_to_telegram = 1 
                WHERE id = ?
            ''', (rec_id,))
            conn.commit()
    
    def get_unsent_recommendations(self) -> List[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, recommendation_type, message, glucose_value
                FROM recommendations
                WHERE sent_to_telegram = 0
                ORDER BY timestamp ASC
            ''')
            return cursor.fetchall()
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        cutoff_datetime = datetime.fromtimestamp(cutoff_date)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM glucose_readings 
                WHERE timestamp < ?
            ''', (cutoff_datetime.isoformat(),))
            
            cursor.execute('''
                DELETE FROM recommendations 
                WHERE timestamp < ? AND sent_to_telegram = 1
            ''', (cutoff_datetime.isoformat(),))
            
            conn.commit()
            logger.info(f"Cleaned up data older than {days_to_keep} days")
    
    def insert_insulin_entry(self, entry: InsulinEntry) -> int:
        """Insert insulin entry into database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO insulin_entries 
                (timestamp, units, insulin_type, duration_minutes, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                entry.timestamp.isoformat(),
                entry.units,
                entry.insulin_type,
                entry.duration_minutes,
                entry.notes
            ))
            conn.commit()
            entry_id = cursor.lastrowid
            logger.info(f"Inserted insulin entry: {entry.units} units {entry.insulin_type}")
            return entry_id or 0
    
    def insert_carb_entry(self, entry: CarbEntry) -> int:
        """Insert carbohydrate entry into database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO carb_entries 
                (timestamp, grams, carb_type, absorption_minutes, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                entry.timestamp.isoformat(),
                entry.grams,
                entry.carb_type,
                entry.absorption_minutes,
                entry.notes
            ))
            conn.commit()
            entry_id = cursor.lastrowid
            logger.info(f"Inserted carb entry: {entry.grams}g {entry.carb_type or 'carbs'}")
            return entry_id or 0
    
    def get_active_insulin(self, current_time: datetime) -> List[InsulinEntry]:
        """Get insulin entries that are still active (within their duration)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, units, insulin_type, duration_minutes, notes
                FROM insulin_entries
                WHERE datetime(timestamp, '+' || duration_minutes || ' minutes') > datetime(?)
                ORDER BY timestamp DESC
            ''', (current_time.isoformat(),))
            
            entries = []
            for row in cursor.fetchall():
                entry = InsulinEntry(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    units=row[2],
                    insulin_type=row[3],
                    duration_minutes=row[4],
                    notes=row[5]
                )
                entries.append(entry)
            
            return entries
    
    def insert_iob_override(self, override: IOBOverride) -> int:
        """Insert IOB override (manual IOB setting)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO iob_overrides 
                (timestamp, iob_value, source, notes)
                VALUES (?, ?, ?, ?)
            ''', (
                override.timestamp.isoformat(),
                override.iob_value,
                override.source,
                override.notes
            ))
            conn.commit()
            override_id = cursor.lastrowid
            logger.info(f"Inserted IOB override: {override.iob_value:.1f}u from {override.source}")
            return override_id or 0
    
    def get_latest_iob_override(self, current_time: datetime, max_age_minutes: int = 30) -> Optional[IOBOverride]:
        """Get most recent IOB override within time limit"""
        cutoff_time = current_time - timedelta(minutes=max_age_minutes)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, iob_value, source, notes
                FROM iob_overrides
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (cutoff_time.isoformat(),))
            
            row = cursor.fetchone()
            if row:
                return IOBOverride(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    iob_value=row[2],
                    source=row[3],
                    notes=row[4]
                )
            
            return None
    
    def get_active_carbs(self, current_time: datetime) -> List[CarbEntry]:
        """Get carb entries that are still being absorbed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, grams, carb_type, absorption_minutes, notes
                FROM carb_entries
                WHERE datetime(timestamp, '+' || absorption_minutes || ' minutes') > datetime(?)
                ORDER BY timestamp DESC
            ''', (current_time.isoformat(),))
            
            entries = []
            for row in cursor.fetchall():
                entry = CarbEntry(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    grams=row[2],
                    carb_type=row[3],
                    absorption_minutes=row[4],
                    notes=row[5]
                )
                entries.append(entry)
            
            return entries
    
    def insert_iob_override(self, override: IOBOverride) -> int:
        """Insert IOB override (manual IOB setting)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO iob_overrides 
                (timestamp, iob_value, source, notes)
                VALUES (?, ?, ?, ?)
            ''', (
                override.timestamp.isoformat(),
                override.iob_value,
                override.source,
                override.notes
            ))
            conn.commit()
            override_id = cursor.lastrowid
            logger.info(f"Inserted IOB override: {override.iob_value:.1f}u from {override.source}")
            return override_id or 0
    
    def get_latest_iob_override(self, current_time: datetime, max_age_minutes: int = 30) -> Optional[IOBOverride]:
        """Get most recent IOB override within time limit"""
        cutoff_time = current_time - timedelta(minutes=max_age_minutes)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, iob_value, source, notes
                FROM iob_overrides
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (cutoff_time.isoformat(),))
            
            row = cursor.fetchone()
            if row:
                return IOBOverride(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    iob_value=row[2],
                    source=row[3],
                    notes=row[4]
                )
            
            return None
    
    def get_recent_insulin_entries(self, hours: int = 6) -> List[InsulinEntry]:
        """Get insulin entries from the last N hours"""
        since_time = datetime.now() - timedelta(hours=hours)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, units, insulin_type, duration_minutes, notes
                FROM insulin_entries
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            ''', (since_time.isoformat(),))
            
            entries = []
            for row in cursor.fetchall():
                entry = InsulinEntry(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    units=row[2],
                    insulin_type=row[3],
                    duration_minutes=row[4],
                    notes=row[5]
                )
                entries.append(entry)
            
            return entries
    
    def insert_iob_override(self, override: IOBOverride) -> int:
        """Insert IOB override (manual IOB setting)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO iob_overrides 
                (timestamp, iob_value, source, notes)
                VALUES (?, ?, ?, ?)
            ''', (
                override.timestamp.isoformat(),
                override.iob_value,
                override.source,
                override.notes
            ))
            conn.commit()
            override_id = cursor.lastrowid
            logger.info(f"Inserted IOB override: {override.iob_value:.1f}u from {override.source}")
            return override_id or 0
    
    def get_latest_iob_override(self, current_time: datetime, max_age_minutes: int = 30) -> Optional[IOBOverride]:
        """Get most recent IOB override within time limit"""
        cutoff_time = current_time - timedelta(minutes=max_age_minutes)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, iob_value, source, notes
                FROM iob_overrides
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (cutoff_time.isoformat(),))
            
            row = cursor.fetchone()
            if row:
                return IOBOverride(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    iob_value=row[2],
                    source=row[3],
                    notes=row[4]
                )
            
            return None
    
    def get_recent_carb_entries(self, hours: int = 4) -> List[CarbEntry]:
        """Get carb entries from the last N hours"""
        since_time = datetime.now() - timedelta(hours=hours)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, grams, carb_type, absorption_minutes, notes
                FROM carb_entries
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            ''', (since_time.isoformat(),))
            
            entries = []
            for row in cursor.fetchall():
                entry = CarbEntry(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    grams=row[2],
                    carb_type=row[3],
                    absorption_minutes=row[4],
                    notes=row[5]
                )
                entries.append(entry)
            
            return entries
    
    def insert_iob_override(self, override: IOBOverride) -> int:
        """Insert IOB override (manual IOB setting)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO iob_overrides 
                (timestamp, iob_value, source, notes)
                VALUES (?, ?, ?, ?)
            ''', (
                override.timestamp.isoformat(),
                override.iob_value,
                override.source,
                override.notes
            ))
            conn.commit()
            override_id = cursor.lastrowid
            logger.info(f"Inserted IOB override: {override.iob_value:.1f}u from {override.source}")
            return override_id or 0
    
    def get_latest_iob_override(self, current_time: datetime, max_age_minutes: int = 30) -> Optional[IOBOverride]:
        """Get most recent IOB override within time limit"""
        cutoff_time = current_time - timedelta(minutes=max_age_minutes)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, iob_value, source, notes
                FROM iob_overrides
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (cutoff_time.isoformat(),))
            
            row = cursor.fetchone()
            if row:
                return IOBOverride(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    iob_value=row[2],
                    source=row[3],
                    notes=row[4]
                )
            
            return None    
    def insert_glucose_note(self, note: GlucoseNote) -> int:
        """Insert glucose note into database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO glucose_notes 
                (timestamp, note_text, note_type, glucose_value, context_data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                note.timestamp.isoformat(),
                note.note_text,
                note.note_type,
                note.glucose_value,
                note.context_data
            ))
            conn.commit()
            note_id = cursor.lastrowid
            logger.info(f"Inserted glucose note: {note.note_type} - {note.note_text[:50]}...")
            return note_id or 0
    
    def get_recent_notes(self, hours: int = 24, note_type: Optional[str] = None) -> List[GlucoseNote]:
        """Get recent glucose notes"""
        since_time = datetime.now() - timedelta(hours=hours)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if note_type:
                cursor.execute("""
                    SELECT id, timestamp, note_text, note_type, glucose_value, context_data
                    FROM glucose_notes
                    WHERE timestamp >= ? AND note_type = ?
                    ORDER BY timestamp DESC
                """, (since_time.isoformat(), note_type))
            else:
                cursor.execute("""
                    SELECT id, timestamp, note_text, note_type, glucose_value, context_data
                    FROM glucose_notes
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (since_time.isoformat(),))
            
            notes = []
            for row in cursor.fetchall():
                note = GlucoseNote(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    note_text=row[2],
                    note_type=row[3],
                    glucose_value=row[4],
                    context_data=row[5]
                )
                notes.append(note)
            
            return notes
