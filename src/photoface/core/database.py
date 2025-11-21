import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path='photo_face_manager.db'):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Таблица с папками
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица с изображениями
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_id INTEGER NOT NULL,
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER,
                    created_time TIMESTAMP,
                    scan_status TEXT DEFAULT 'pending', -- pending, processing, completed, error
                    FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE
                )
            ''')

            # Таблица с персонами
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS persons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT DEFAULT 'not recognized',
                    is_confirmed BOOLEAN DEFAULT FALSE,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица с лицами
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER NOT NULL,
                    person_id INTEGER NOT NULL,
                    embedding BLOB,
                    bbox_x1 REAL,
                    bbox_y1 REAL,
                    bbox_x2 REAL,
                    bbox_y2 REAL,
                    confidence REAL,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE,
                    FOREIGN KEY (person_id) REFERENCES persons (id) ON DELETE CASCADE
                )
            ''')

            # Таблица для альбомов (связь персона -> выходная папка)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS albums (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id INTEGER UNIQUE NOT NULL,
                    output_path TEXT,
                    FOREIGN KEY (person_id) REFERENCES persons (id) ON DELETE CASCADE
                )
            ''')

            conn.commit()

    # методы для работы с папками
    def add_folder(self, folder_path):
        """Добавляет папку в базу данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO folders (path) VALUES (?)",
                    (folder_path,)
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None

    def remove_folder(self, folder_path):
        """Удаляет папку из базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM folders WHERE path = ?", (folder_path,))
            conn.commit()
            return cursor.rowcount > 0

    def get_all_folders(self):
        """Возвращает все добавленные папки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, path, added_date FROM folders ORDER BY added_date")
            return cursor.fetchall()

    def folder_exists(self, folder_path):
        """Проверяет, существует ли папка в базе"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            return cursor.fetchone() is not None
        
    # Методы для работы с изображениями и лицами
    def add_image(self, folder_id, file_path, file_name, file_size, created_time):
        """Добавляет изображение в базу данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO images 
                    (folder_id, file_path, file_name, file_size, created_time) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (folder_id, file_path, file_name, file_size, created_time))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Если изображение уже существует, возвращаем его ID
                cursor.execute("SELECT id FROM images WHERE file_path = ?", (file_path,))
                result = cursor.fetchone()
                return result[0] if result else None

    def get_pending_images(self, folder_id=None):
        """Возвращает изображения, ожидающие обработки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if folder_id:
                cursor.execute('''
                    SELECT id, file_path FROM images 
                    WHERE folder_id = ? AND scan_status = 'pending'
                ''', (folder_id,))
            else:
                cursor.execute('''
                    SELECT id, file_path FROM images 
                    WHERE scan_status = 'pending'
                ''')
            return cursor.fetchall()

    def update_image_status(self, image_id, status):
        """Обновляет статус обработки изображения"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE images SET scan_status = ? WHERE id = ?",
                (status, image_id)
            )
            conn.commit()

    def create_person(self, name='not recognized'):
        """Создает новую персону"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO persons (name) VALUES (?)",
                (name,)
            )
            conn.commit()
            return cursor.lastrowid

    def add_face(self, image_id, person_id, embedding, bbox, confidence):
        """Добавляет найденное лицо в базу данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO faces 
                (image_id, person_id, embedding, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (image_id, person_id, embedding, 
                  bbox[0], bbox[1], bbox[2], bbox[3], confidence))
            conn.commit()
            return cursor.lastrowid

    def get_person_by_name(self, name):
        """Находит персону по имени"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM persons WHERE name = ?", (name,))
            result = cursor.fetchone()
            return result[0] if result else None

    def image_already_processed(self, file_path):
        """Проверяет, было ли изображение уже обработано"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM images 
                WHERE file_path = ? AND scan_status = 'completed'
            ''', (file_path,))
            return cursor.fetchone() is not None

    def get_folder_images_count(self, folder_id):
        """Возвращает количество изображений в папке"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM images WHERE folder_id = ?",
                (folder_id,)
            )
            return cursor.fetchone()[0]

    def get_processed_images_count(self, folder_id=None):
        """Возвращает количество обработанных изображений"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if folder_id:
                cursor.execute('''
                    SELECT COUNT(*) FROM images 
                    WHERE folder_id = ? AND scan_status = 'completed'
                ''', (folder_id,))
            else:
                cursor.execute('''
                    SELECT COUNT(*) FROM images 
                    WHERE scan_status = 'completed'
                ''')
            return cursor.fetchone()[0]