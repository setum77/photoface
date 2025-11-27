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
        try:
            # Получаем список папок для сканирования
            if self.folder_id:
                # Получаем информацию о конкретной папке
                folder_info = self.db_manager.get_folder_by_id(self.folder_id)
                if folder_info:
                    folders = [(folder_info[0], folder_info[1])]  # (folder_id, folder_path)
                    logger.info(f"Сканирование папки: {folder_info[1]}")
                else:
                    logger.error(f"Папка с ID {self.folder_id} не найдена")
                    return
            else:
                # Получаем все папки
                folders_data = self.db_manager.get_all_folders()
                folders = []
                for folder_data in folders_data:
                    if len(folder_data) >= 2:  # Проверяем, что есть как минимум ID и путь
                        folders.append((folder_data[0], folder_data[1]))
                        logger.info(f"Найдена папка для сканирования: {folder_data[1]}")

                    else:
                        logger.warning(f"Некорректные данные папки: {folder_data}")

            if not folders:
                logger.info("Нет папок для сканирования")
                return

            total_images = 0
            processed_images = 0
            
            # Подсчитываем общее количество изображений
            for folder_id, folder_path in folders:
                try:
                    image_files = get_image_files(folder_path)
                    total_images += len(image_files)
                    logger.info(f"Папка {folder_path}: {len(image_files)} изображений")
                    for img in image_files[:5]:  # Логируем первые 5 файлов
                        logger.debug(f"  - {img}")
                except Exception as e:
                    logger.error(f"Ошибка при получении файлов из папки {folder_path}: {e}")

            if total_images == 0:
                logger.info("Нет изображений для обработки")
                return

            # Создаем персону "not recognized" по умолчанию
            not_recognized_id = self.db_manager.get_person_by_name('not recognized')
            if not not_recognized_id:
                not_recognized_id = self.db_manager.create_person('not recognized')
                logger.info(f"Создана персона 'not recognized' с ID: {not_recognized_id}")

            # Обрабатываем каждую папку
            for folder_id, folder_path in folders:
                if self.is_cancelled:
                    logger.info("Сканирование отменено")
                    break
                    
                logger.info(f"Сканирование папки: {folder_path} (ID: {folder_id})")
                
                # Получаем список изображений в папке
                try:
                    image_files = get_image_files(folder_path)
                    logger.info(f"Найдено {len(image_files)} изображений в папке {folder_path}")
                except Exception as e:
                    logger.error(f"Ошибка при получении изображений из папки {folder_path}: {e}")
                    continue
                
                for image_path in image_files:
                    if self.is_cancelled:
                        logger.info("Сканирование отменено")
                        break
                        
                    processed_images += 1
                    self.signals.progress_updated.emit(
                        processed_images, total_images, os.path.basename(image_path)
                    )

                    # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ПРОВЕРКИ
                    is_processed = self.db_manager.image_already_processed(image_path)
                    logger.debug(f"Изображение {os.path.basename(image_path)}: уже обработано = {is_processed}")
                    
                    if is_processed:
                        logger.debug(f"Пропускаем уже обработанное изображение: {image_path}")
                        continue

                    image_id = None
                    try:
                        # Получаем информацию о файле
                        file_stats = os.stat(image_path)
                        file_size = file_stats.st_size
                        created_time = datetime.fromtimestamp(file_stats.st_ctime)

                        # ДОБАВЛЯЕМ ЛОГИРОВАНИЕ ДОБАВЛЕНИЯ ИЗОБРАЖЕНИЯ
                        logger.debug(f"Добавляем изображение в БД: {os.path.basename(image_path)}")
                        image_id = self.db_manager.add_image(
                            folder_id, image_path, os.path.basename(image_path), 
                            file_size, created_time
                        )

                        if not image_id:
                            logger.error(f"Не удалось добавить изображение в БД: {image_path}")
                            continue

                        logger.debug(f"Изображение добавлено с ID: {image_id}")

                        # Обновляем статус на 'processing'
                        self.db_manager.update_image_status(image_id, 'processing')

                        # Детекция лиц
                        logger.info(f"Детекция лиц в изображении: {os.path.basename(image_path)}")
                        faces = self.face_analyzer.detect_faces(image_path)
                        logger.info(f"Найдено {len(faces)} лиц в изображении {os.path.basename(image_path)}")

                        # Сохраняем найденные лица
                        face_count = 0
                        for face in faces:
                            # Распаковываем координаты bounding box
                            bbox = face['bbox']
                            x1, y1, x2, y2 = bbox

                            face_id = self.db_manager.add_face(
                                image_id=image_id,
                                person_id=not_recognized_id,
                                embedding=face['embedding'],
                                bbox=bbox,
                                confidence=face['confidence']
                            )
                            if face_id:
                                face_count += 1
                                logger.debug(f"Добавлено лицо с ID: {face_id}")
                            else:
                                logger.error(f"Не удалось добавить лицо в БД для изображения {image_path}")

                        logger.info(f"Сохранено {face_count} лиц для изображения {os.path.basename(image_path)}")

                        # Обновляем статус на 'completed'
                        self.db_manager.update_image_status(image_id, 'completed')
                        logger.info(f"Обработано изображение: {os.path.basename(image_path)} - {len(faces)} лиц")

                    except Exception as e:
                        logger.error(f"Ошибка обработки изображения {image_path}: {e}")
                        # Помечаем изображение как ошибочное
                        if image_id:
                            self.db_manager.update_image_status(image_id, 'error')
                    
                logger.info(f"Сканирование завершено. Обработано {processed_images}/{total_images} изображений")
                                
        except Exception as e:
            logger.error(f"Критическая ошибка в процессе сканирования: {e}")
            raise

class ScanManager:
    """Менеджер сканирования для координации процессов"""
    
    def __init__(self, db_manager, config=None):
        self.db_manager = db_manager
        self.config = config
        self.face_analyzer = FaceAnalyzer(config)
        self.thread_pool = QThreadPool()
        self.current_task = None
        
        # Инициализируем модель распознавания
        if not self.face_analyzer.initialize():
            raise Exception("Не удалось инициализировать модель распознавания лиц")
            
    def update_config(self, config):
        """Обновляет конфигурацию и перезапускает анализатор при необходимости"""
        self.config = config
        self.face_analyzer.config = config

    def start_scan(self, folder_id=None):
        """Начинает процесс сканирования"""
        if self.current_task and not self.current_task.is_cancelled:
            logger.warning("Сканирование уже выполняется")
            return False

        self.current_task = ScanTask(self.db_manager, self.face_analyzer, folder_id)
        self.thread_pool.start(self.current_task)
        logger.info("Запущено новое сканирование")
        return True

    def cancel_scan(self):
        """Отменяет текущее сканирование"""
        if self.current_task:
            self.current_task.cancel()
            logger.info("Запрос на отмену сканирования")

    def is_scanning(self):
        """Проверяет, выполняется ли сканирование"""
        return (self.current_task is not None and 
                not self.current_task.is_cancelled and
                self.thread_pool.activeThreadCount() > 0)
    
    # Временный метод для тестирования
    def test_single_image(self, image_path):
        """Тестирует обработку одного изображения"""
        logger.info(f"=== ТЕСТИРУЕМ ИЗОБРАЖЕНИЕ: {image_path} ===")
        
        # Проверяем поддержку формата
        self.face_analyzer.check_image_support(image_path)
        
        # Пробуем детекцию
        faces = self.face_analyzer.detect_faces(image_path)
        logger.info(f"Результат теста: {len(faces)} лиц")
        
        return len(faces) > 0