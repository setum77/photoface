import os
import time
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
import logging
from src.photoface.core.database import DatabaseManager
from src.photoface.core.face_analyzer import FaceAnalyzer
from src.photoface.utils.helpers import get_image_files

logger = logging.getLogger(__name__)

class ScanSignals(QObject):
    """Сигналы для сканирования"""
    progress_updated = pyqtSignal(int, int, str)  # текущий, всего, имя файла
    scan_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

class ScanTask(QRunnable):
    """Задача сканирования для выполнения в отдельном потоке"""
    
    def __init__(self, db_manager, face_analyzer, folder_id=None):
        super().__init__()
        self.db_manager = db_manager
        self.face_analyzer = face_analyzer
        self.folder_id = folder_id
        self.signals = ScanSignals()
        self.is_cancelled = False

    def run(self):
        try:
            self._scan_folders()
            self.signals.scan_finished.emit()
        except Exception as e:
            logger.error(f"Ошибка при сканировании: {e}")
            self.signals.error_occurred.emit(str(e))

    def cancel(self):
        self.is_cancelled = True

    def _scan_folders(self):
        """Основной метод сканирования"""
        # Получаем список папок для сканирования
        if self.folder_id:
            folders = [(self.folder_id, "Selected Folder")]
        else:
            folders = self.db_manager.get_all_folders()

        total_images = 0
        processed_images = 0
        
        # Подсчитываем общее количество изображений
        for folder_id, folder_path in folders:
            image_files = get_image_files(folder_path)
            total_images += len(image_files)

        # Создаем персону "not recognized" по умолчанию
        not_recognized_id = self.db_manager.get_person_by_name('not recognized')
        if not not_recognized_id:
            not_recognized_id = self.db_manager.create_person('not recognized')

        # Обрабатываем каждую папку
        for folder_id, folder_path in folders:
            if self.is_cancelled:
                break
                
            logger.info(f"Сканирование папки: {folder_path}")
            
            # Получаем список изображений в папке
            image_files = get_image_files(folder_path)
            
            for image_path in image_files:
                if self.is_cancelled:
                    break
                    
                processed_images += 1
                self.signals.progress_updated.emit(
                    processed_images, total_images, os.path.basename(image_path)
                )

                # Проверяем, не было ли изображение уже обработано
                if self.db_manager.image_already_processed(image_path):
                    logger.debug(f"Изображение уже обработано: {image_path}")
                    continue

                try:
                    # Получаем информацию о файле
                    file_stats = os.stat(image_path)
                    file_size = file_stats.st_size
                    created_time = datetime.fromtimestamp(file_stats.st_ctime)

                    # Добавляем изображение в БД
                    image_id = self.db_manager.add_image(
                        folder_id, image_path, os.path.basename(image_path), 
                        file_size, created_time
                    )

                    if not image_id:
                        logger.error(f"Не удалось добавить изображение в БД: {image_path}")
                        continue

                    # Обновляем статус на 'processing'
                    self.db_manager.update_image_status(image_id, 'processing')

                    # Детекция лиц
                    faces = self.face_analyzer.detect_faces(image_path)

                    # Сохраняем найденные лица
                    for face in faces:
                        self.db_manager.add_face(
                            image_id=image_id,
                            person_id=not_recognized_id,  # Пока все лица в "not recognized"
                            embedding=face['embedding'],
                            bbox=face['bbox'],
                            confidence=face['confidence']
                        )

                    # Обновляем статус на 'completed'
                    self.db_manager.update_image_status(image_id, 'completed')
                    logger.info(f"Обработано изображение: {os.path.basename(image_path)} - {len(faces)} лиц")

                except Exception as e:
                    logger.error(f"Ошибка обработки изображения {image_path}: {e}")
                    # Помечаем изображение как ошибочное
                    if 'image_id' in locals():
                        self.db_manager.update_image_status(image_id, 'error')

class ScanManager:
    """Менеджер сканирования для координации процессов"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.face_analyzer = FaceAnalyzer()
        self.thread_pool = QThreadPool()
        self.current_task = None
        
        # Инициализируем модель распознавания
        if not self.face_analyzer.initialize():
            raise Exception("Не удалось инициализировать модель распознавания лиц")

    def start_scan(self, folder_id=None):
        """Начинает процесс сканирования"""
        if self.current_task and not self.current_task.is_cancelled:
            return False

        self.current_task = ScanTask(self.db_manager, self.face_analyzer, folder_id)
        self.thread_pool.start(self.current_task)
        return True

    def cancel_scan(self):
        """Отменяет текущее сканирование"""
        if self.current_task:
            self.current_task.cancel()

    def is_scanning(self):
        """Проверяет, выполняется ли сканирование"""
        return (self.current_task is not None and 
                not self.current_task.is_cancelled and
                self.thread_pool.activeThreadCount() > 0)