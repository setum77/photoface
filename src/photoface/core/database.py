import logging
import sqlite3
import os
import numpy as np
from datetime import datetime
from typing import List, Tuple, Optional    

logger = logging.getLogger(__name__)

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
                    orig_width INTEGER DEFAULT 0,
                    orig_height INTEGER DEFAULT 0,
                    created_time TIMESTAMP,
                    scan_status TEXT DEFAULT 'pending', -- pending, processing, completed, error
                    FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE
                )
            ''')
            # Авто-добавляем колонки если отсутствуют (миграция)
            cursor.execute("PRAGMA table_info(images)")
            cols = {row[1] for row in cursor.fetchall()}
            if 'orig_width' not in cols:
                cursor.execute("ALTER TABLE images ADD COLUMN orig_width INTEGER DEFAULT 0")
            if 'orig_height' not in cols:
                cursor.execute("ALTER TABLE images ADD COLUMN orig_height INTEGER DEFAULT 0")

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
                    is_person BOOLEAN DEFAULT 0,
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
            
            # Таблица для настроек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY NOT NULL,
                    value TEXT
                )
            ''')

            conn.commit()

    # методы для работы с папками
    # def add_folder(self, folder_path):
    #     """Добавляет папку в базу данных"""
    #     with self.get_connection() as conn:
    #         cursor = conn.cursor()
    #         try:
    #             cursor.execute(
    #                 "INSERT OR IGNORE INTO folders (path) VALUES (?)",
    #                 (folder_path,)
    #             )
    #             conn.commit()
    #             return cursor.lastrowid
    #         except sqlite3.IntegrityError:
    #             return None
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
                folder_id = cursor.lastrowid
                if folder_id:
                    logger.info(f"Добавлена папка: {folder_path} (ID: {folder_id})")
                else:
                    logger.warning(f"Папка уже существует: {folder_path}")
                return folder_id
            except sqlite3.IntegrityError:
                logger.warning(f"Попытка добавить существующую папку: {folder_path}")
                return None
            except Exception as e:
                logger.error(f"Ошибка при добавлении папки {folder_path}: {e}")
                return None

    def remove_folder(self, folder_path):
        """Удаляет папку из базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM folders WHERE path = ?", (folder_path,))
            conn.commit()
            return cursor.rowcount > 0

    # def get_all_folders(self):
    #     """Возвращает все добавленные папки"""
    #     with self.get_connection() as conn:
    #         cursor = conn.cursor()
    #         cursor.execute("SELECT id, path, added_date FROM folders ORDER BY added_date")
    #         return cursor.fetchall()
    def get_folder_by_id(self, folder_id):
        """Получает информацию о папке по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT id, path, added_date FROM folders WHERE id = ?", 
                    (folder_id,)
                )
                folder = cursor.fetchone()
                if folder:
                    logger.debug(f"Найдена папка: ID={folder[0]}, путь={folder[1]}")
                else:
                    logger.warning(f"Папка с ID {folder_id} не найдена")
                return folder
            except Exception as e:
                logger.error(f"Ошибка при получении папки {folder_id} из БД: {e}")
                return None

    def get_all_folders(self):
        """Возвращает все добавленные папки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT id, path, added_date FROM folders ORDER BY added_date")
                folders = cursor.fetchall()
                logger.debug(f"Получено {len(folders)} папок из БД")
                return folders
            except Exception as e:
                logger.error(f"Ошибка при получении папок из БД: {e}")
                return []

    def folder_exists(self, folder_path):
        """Проверяет, существует ли папка в базе"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM folders WHERE path = ?", (folder_path,))
            return cursor.fetchone() is not None
        
    # Методы для работы с изображениями и лицами
    # def add_image(self, folder_id, file_path, file_name, file_size, created_time):
    #     """Добавляет изображение в базу данных"""
    #     with self.get_connection() as conn:
    #         cursor = conn.cursor()
    #         try:
    #             cursor.execute('''
    #                 INSERT OR IGNORE INTO images 
    #                 (folder_id, file_path, file_name, file_size, created_time) 
    #                 VALUES (?, ?, ?, ?, ?)
    #             ''', (folder_id, file_path, file_name, file_size, created_time))
    #             conn.commit()
    #             return cursor.lastrowid
    #         except sqlite3.IntegrityError:
    #             # Если изображение уже существует, возвращаем его ID
    #             cursor.execute("SELECT id FROM images WHERE file_path = ?", (file_path,))
    #             result = cursor.fetchone()
    #             return result[0] if result else None
    def add_image(self, folder_id, file_path, file_name, file_size, created_time):
        """Добавляет изображение в базу данных"""
        orig_w, orig_h = 0, 0
        try:
            from PIL import Image  # Импорт внутри для избежания ошибок
            with Image.open(file_path) as img:
                orig_w, orig_h = img.size
        except Exception as e:
            logger.warning(f"Не удалось получить размер {file_path}: {e}")
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO images 
                    (folder_id, file_path, file_name, file_size, orig_width, orig_height, created_time) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (folder_id, file_path, file_name, file_size, orig_w, orig_h, created_time))
                conn.commit()
                image_id = cursor.lastrowid
                if image_id:
                    logger.debug(f"Добавлено изображение {file_path}: {orig_w}x{orig_h} (ID: {image_id})")
                return image_id
            except sqlite3.IntegrityError:
                cursor.execute("SELECT id FROM images WHERE file_path = ?", (file_path,))
                result = cursor.fetchone()
                return result[0] if result else None
            except Exception as e:
                logger.error(f"Ошибка add_image {file_path}: {e}")
                return None

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

    # def add_face(self, image_id, person_id, embedding, bbox, confidence):
    #     """Добавляет найденное лицо в базу данных"""
    #     with self.get_connection() as conn:
    #         cursor = conn.cursor()
    #         cursor.execute('''
    #             INSERT INTO faces 
    #             (image_id, person_id, embedding, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence)
    #             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    #         ''', (image_id, person_id, embedding, 
    #               bbox[0], bbox[1], bbox[2], bbox[3], confidence))
    #         conn.commit()
    #         return cursor.lastrowid
    def add_face(self, image_id, person_id, embedding, bbox, confidence):
        """Добавляет найденное лицо в базу данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ
                logger.debug(f"Добавление лица: image_id={image_id}, bbox={bbox}, confidence={confidence}")
                
                # Проверяем и конвертируем координаты
                if isinstance(bbox, (tuple, list)) and len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
                else:
                    logger.error(f"Некорректный формат bbox: {bbox}")
                    return None
                
                cursor.execute('''
                    INSERT INTO faces
                    (image_id, person_id, embedding, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, is_person)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (image_id, person_id, embedding,
                    x1, y1, x2, y2, confidence, 0))
                conn.commit()
                face_id = cursor.lastrowid
                logger.debug(f"Добавлено лицо: image_id={image_id}, person_id={person_id}, confidence={confidence:.3f}, bbox=({x1},{y1},{x2},{y2})")
                return face_id
            except Exception as e:
                logger.error(f"Ошибка при добавлении лица для image_id={image_id}: {e}")
                logger.error(f"bbox={bbox}, confidence={confidence}")
                return None

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
            result = cursor.fetchone()
            
            # ДОБАВЬТЕ ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ
            if result:
                logger.debug(f"Изображение {file_path} уже обработано (ID: {result[0]})")
            else:
                logger.debug(f"Изображение {file_path} еще не обработано")
                
            return result is not None

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
    
    # Методы для работы с персонами и группировкой
    def get_all_persons(self, include_unconfirmed=True):
        """Возвращает всех персон из базы данных"""
					   
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if include_unconfirmed:
                cursor.execute('''
                    SELECT id, name, is_confirmed, created_date 
                    FROM persons 
                    ORDER BY is_confirmed DESC, name
                ''')
            else:
                cursor.execute('''
                    SELECT id, name, is_confirmed, created_date 
                    FROM persons 
                    WHERE is_confirmed = TRUE
                    ORDER BY name
                ''')
            return cursor.fetchall()

    def get_person_faces(self, person_id):
        """Возвращает все лица, принадлежащие персоне"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, f.image_id, i.file_path, f.bbox_x1, f.bbox_y1,
                       f.bbox_x2, f.bbox_y2, f.confidence, f.is_person
                FROM faces f
                JOIN images i ON f.image_id = i.id
                WHERE f.person_id = ?
                ORDER BY f.confidence DESC
            ''', (person_id,))
            return cursor.fetchall()

    def get_face_embedding(self, face_id):
        """Возвращает эмбеддинг лица"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT embedding FROM faces WHERE id = ?
            ''', (face_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def get_all_face_embeddings(self):
        """Возвращает все эмбеддинги лиц для кластеризации"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, f.embedding, p.name, f.is_person
                FROM faces f
                JOIN persons p ON f.person_id = p.id
                WHERE p.name = 'not recognized'
            ''')
            return cursor.fetchall()

    def update_person_name(self, person_id, new_name):
        """Обновляет имя персоны"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE persons SET name = ? WHERE id = ?
            ''', (new_name, person_id))
            conn.commit()
            return cursor.rowcount > 0

    def confirm_person(self, person_id):
        """Подтверждает персону"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE persons SET is_confirmed = TRUE WHERE id = ?
            ''', (person_id,))
            conn.commit()
            return cursor.rowcount > 0

    def merge_persons(self, source_person_id, target_person_id):
        """Объединяет две персоны в одну"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Перемещаем все лица из source в target
            cursor.execute('''
                UPDATE faces SET person_id = ? WHERE person_id = ?
            ''', (target_person_id, source_person_id))
            # Удаляем пустую персону
            cursor.execute('''
                DELETE FROM persons WHERE id = ?
            ''', (source_person_id,))
            conn.commit()
            return cursor.rowcount > 0

    def move_face_to_person(self, face_id, new_person_id):
        """Перемещает лицо к другой персоне"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE faces SET person_id = ? WHERE id = ?
            ''', (new_person_id, face_id))
            conn.commit()
            return cursor.rowcount > 0

    def set_face_person_status(self, face_id, is_person):
        """Устанавливает статус подтверждения принадлежности лица персоне"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE faces SET is_person = ? WHERE id = ?
            ''', (is_person, face_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_face_person_status(self, face_id):
        """Возвращает статус подтверждения принадлежности лица персоне"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_person FROM faces WHERE id = ?
            ''', (face_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def create_new_person_from_face(self, face_id, person_name):
        """Создает новую персону и перемещает в нее лицо"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Создаем новую персону
            person_id = self.create_person(person_name)
            if person_id:
                # Перемещаем лицо
                self.move_face_to_person(face_id, person_id)
            return person_id

    def get_person_stats(self):
        """Возвращает статистику по персонам"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.id, p.name, p.is_confirmed, COUNT(f.id) as face_count
                FROM persons p
                LEFT JOIN faces f ON p.id = f.person_id
                GROUP BY p.id, p.name, p.is_confirmed
                ORDER BY p.is_confirmed DESC, face_count DESC
            ''')
            return cursor.fetchall()

    def get_unrecognized_faces_count(self):
        """Возвращает количество нераспознанных лиц"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) 
                FROM faces f
                JOIN persons p ON f.person_id = p.id
                WHERE p.name = 'not recognized'
            ''')
            return cursor.fetchone()[0]
        
    # Метод для получения информации о лицах изображения
    def get_image_faces(self, image_path):
        """Возвращает все лица для указанного изображения"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2,
                    f.confidence, p.name, p.id as person_id, f.is_person
                FROM faces f
                JOIN images i ON f.image_id = i.id
                JOIN persons p ON f.person_id = p.id
                WHERE i.file_path = ?
            ''', (image_path,))
            return cursor.fetchall()
    
    # Методы для работы с альбомами
    def set_album_output_path(self, person_id, output_path):
        """Устанавливает путь для альбома персоны"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO albums (person_id, output_path)
                VALUES (?, ?)
            ''', (person_id, output_path))
            conn.commit()
            return cursor.rowcount > 0

    def get_album_output_path(self, person_id):
        """Возвращает путь альбома для персоны"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT output_path FROM albums WHERE person_id = ?
            ''', (person_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def get_persons_with_albums(self):
        """Возвращает персон с настроенными альбомами"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.id, p.name, p.is_confirmed, a.output_path
                FROM persons p
                JOIN albums a ON p.id = a.person_id
                WHERE p.is_confirmed = TRUE
                ORDER BY p.name
            ''')
            return cursor.fetchall()

    def get_person_photos(self, person_id):
        """Возвращает все фотографии с лицом персоны"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT 
                    i.file_path,
                    i.file_name,
                    (SELECT COUNT(*) 
                     FROM faces f2 
                     JOIN images i2 ON f2.image_id = i2.id 
                     WHERE i2.file_path = i.file_path) as total_faces,
                    f.confidence
                FROM faces f
                JOIN images i ON f.image_id = i.id
                WHERE f.person_id = ?
                ORDER BY total_faces, f.confidence DESC
            ''', (person_id,))
            return cursor.fetchall()

    def get_photos_with_multiple_faces(self, person_id):
        """Возвращает фотографии где персона находится с другими людьми"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT 
                    i.file_path,
                    i.file_name,
                    (SELECT GROUP_CONCAT(p2.name, ', ') 
                     FROM faces f2 
                     JOIN persons p2 ON f2.person_id = p2.id 
                     WHERE f2.image_id = i.id AND p2.is_confirmed = TRUE) as other_persons
                FROM faces f
                JOIN images i ON f.image_id = i.id
                WHERE f.person_id = ? 
                AND (SELECT COUNT(*) FROM faces f2 WHERE f2.image_id = i.id) > 1
                ORDER BY i.file_name
            ''', (person_id,))
            return cursor.fetchall()

    def get_single_photos(self, person_id):
        """Возвращает одиночные фотографии персоны"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT 
                    i.file_path,
                    i.file_name,
                    f.confidence
                FROM faces f
                JOIN images i ON f.image_id = i.id
                WHERE f.person_id = ? 
                AND (SELECT COUNT(*) FROM faces f2 WHERE f2.image_id = i.id) = 1
                ORDER BY f.confidence DESC
            ''', (person_id,))
            return cursor.fetchall()

    def is_album_created(self, person_id):
        """Проверяет, создан ли альбом для персоны"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT output_path FROM albums WHERE person_id = ?
            ''', (person_id,))
            result = cursor.fetchone()
            return result is not None and os.path.exists(result[0])
    
    # Метод для очистки обработанных данных
    def clear_processed_data(self):
        """Очищает все обработанные данные (для тестирования)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM faces")
            cursor.execute("DELETE FROM images")
            cursor.execute("DELETE FROM persons WHERE name != 'not recognized'")
            conn.commit()
            logger.info("Очищены все обработанные данные")

    def get_image_dimensions(self, image_id):
        """Возвращает orig_width, orig_height по image_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT orig_width, orig_height FROM images WHERE id = ?", (image_id,))
            result = cursor.fetchone()
            return result if result else (0, 0)
            
    def update_image_path(self, old_path, new_path):
        """Обновляет путь к изображению в базе данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Обновляем только имя файла, но оставляем полный путь
            new_filename = os.path.basename(new_path)
            cursor.execute('''
                UPDATE images
                SET file_path = ?, file_name = ?
                WHERE file_path = ?
            ''', (new_path, new_filename, old_path))
            conn.commit()
            updated_rows = cursor.rowcount
            logger.debug(f"Обновлено {updated_rows} записей: {old_path} -> {new_path}")
            return updated_rows > 0
            
    # Диагностический метод
    def debug_face_data(self, image_path):
        """Диагностика данных о лицах для изображения"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2, 
                    f.confidence, p.name, i.file_path
                FROM faces f
                JOIN images i ON f.image_id = i.id
                JOIN persons p ON f.person_id = p.id
                WHERE i.file_path = ?
            ''', (image_path,))
            
            faces = cursor.fetchall()
            print(f"=== ДИАГНОСТИКА ДЛЯ {image_path} ===")
            print(f"Найдено лиц: {len(faces)}")
            
            for face_id, x1, y1, x2, y2, confidence, person_name, file_path in faces:
                print(f"Лицо ID {face_id}:")
                print(f"  BBOX: ({x1}, {y1}, {x2}, {y2})")
                print(f"  Confidence: {confidence}")
                print(f"  Person: {person_name}")
                print(f"  Размер bbox: {x2-x1:.1f}x{y2-y1:.1f}")
            
            return faces

    # Методы для работы с настройками
    def get_setting(self, key: str, default=None):
        """Получает значение настройки по ключу"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result[0] if result else default

    def set_setting(self, key: str, value: str):
        """Устанавливает значение настройки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    def get_all_settings(self):
        """Получает все настройки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            return dict(cursor.fetchall())