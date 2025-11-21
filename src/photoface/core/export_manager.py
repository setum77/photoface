import os
import shutil
import logging
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from src.photoface.core.database import DatabaseManager
from src.photoface.utils.helpers import generate_thumbnail

logger = logging.getLogger(__name__)

class ExportSignals(QObject):
    """Сигналы для экспорта"""
    progress_updated = pyqtSignal(int, int, str)  # текущий, всего, описание
    export_finished = pyqtSignal(bool, str)  # success, message
    error_occurred = pyqtSignal(str)

class ExportTask(QRunnable):
    """Задача экспорта для выполнения в отдельном потоке"""
    
    def __init__(self, db_manager, person_id=None):
        super().__init__()
        self.db_manager = db_manager
        self.person_id = person_id
        self.signals = ExportSignals()
        self.is_cancelled = False

    def run(self):
        try:
            success, message = self._export_albums()
            self.signals.export_finished.emit(success, message)
        except Exception as e:
            logger.error(f"Ошибка при экспорте: {e}")
            self.signals.export_finished.emit(False, str(e))
        finally:
            self.is_cancelled = True

    def cancel(self):
        self.is_cancelled = True

    def _export_albums(self):
        """Основной метод экспорта"""
        try:
            if self.person_id:
                # Экспорт только для одной персоны
                persons = [(self.person_id, "Selected Person")]
            else:
                # Экспорт для всех подтвержденных персон с альбомами
                persons = self.db_manager.get_persons_with_albums()

            if not persons:
                return False, "Нет персон с настроенными альбомами"

            total_photos = 0
            processed_photos = 0
            
            # Подсчитываем общее количество фотографий
            for person_id, person_name, _, output_path in persons:
                photos = self.db_manager.get_person_photos(person_id)
                total_photos += len(photos)

            # Экспортируем для каждой персоны
            for person_id, person_name, _, output_path in persons:
                if self.is_cancelled:
                    break
                    
                logger.info(f"Экспорт альбома для: {person_name}")
                
                success, message = self._export_person_album(
                    person_id, person_name, output_path, 
                    processed_photos, total_photos
                )
                
                if not success:
                    return False, message
                    
                # Обновляем счетчик обработанных фото
                photos = self.db_manager.get_person_photos(person_id)
                processed_photos += len(photos)

            return True, f"Экспорт завершен. Обработано {processed_photos} фотографий"
            
        except Exception as e:
            logger.error(f"Ошибка экспорта: {e}")
            return False, f"Ошибка экспорта: {e}"

    def _export_person_album(self, person_id, person_name, output_path, 
                           processed_before, total_photos):
        """Экспортирует альбом для конкретной персоны"""
        try:
            # Создаем основную папку альбома
            album_path = os.path.join(output_path, person_name)
            os.makedirs(album_path, exist_ok=True)
            
            # Создаем папку для фото с друзьями
            friends_path = os.path.join(album_path, "with_friends")
            os.makedirs(friends_path, exist_ok=True)

            # Получаем фотографии
            single_photos = self.db_manager.get_single_photos(person_id)
            group_photos = self.db_manager.get_photos_with_multiple_faces(person_id)

            # Экспортируем одиночные фотографии
            for i, (file_path, file_name, confidence) in enumerate(single_photos):
                if self.is_cancelled:
                    return False, "Экспорт отменен"
                    
                processed_photos = processed_before + i + 1
                self.signals.progress_updated.emit(
                    processed_photos, total_photos, 
                    f"Экспорт {person_name}: {file_name}"
                )

                self._copy_photo(file_path, album_path, file_name)

            # Экспортируем групповые фотографии
            for i, (file_path, file_name, other_persons) in enumerate(group_photos):
                if self.is_cancelled:
                    return False, "Экспорт отменен"
                    
                processed_photos = processed_before + len(single_photos) + i + 1
                self.signals.progress_updated.emit(
                    processed_photos, total_photos,
                    f"Экспорт {person_name} с друзьями: {file_name}"
                )

                self._copy_photo(file_path, friends_path, file_name)

            # Создаем информационный файл
            self._create_info_file(album_path, person_name, 
                                 len(single_photos), len(group_photos))

            logger.info(f"Альбом создан: {album_path} "
                       f"({len(single_photos)} одиночных, "
                       f"{len(group_photos)} с друзьями)")
                       
            return True, "Успех"
            
        except Exception as e:
            logger.error(f"Ошибка экспорта альбома для {person_name}: {e}")
            return False, f"Ошибка экспорта для {person_name}: {e}"

    def _copy_photo(self, source_path, target_dir, filename):
        """Копирует фотографию в целевую директорию"""
        try:
            target_path = os.path.join(target_dir, filename)
            
            # Если файл уже существует, добавляем суффикс
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(target_path):
                new_filename = f"{base_name}_{counter}{ext}"
                target_path = os.path.join(target_dir, new_filename)
                counter += 1
                
            shutil.copy2(source_path, target_path)
            
        except Exception as e:
            logger.error(f"Ошибка копирования {source_path}: {e}")
            raise

    def _create_info_file(self, album_path, person_name, single_count, group_count):
        """Создает информационный файл для альбома"""
        try:
            info_content = f"""Альбом: {person_name}
Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Одиночных фотографий: {single_count}
Фотографий с друзьями: {group_count}
Общее количество: {single_count + group_count}

Создано программой Photo Face Manager
"""
            info_path = os.path.join(album_path, "info.txt")
            with open(info_path, 'w', encoding='utf-8') as f:
                f.write(info_content)
                
        except Exception as e:
            logger.error(f"Ошибка создания info файла: {e}")

class ExportManager:
    """Менеджер экспорта для координации процессов"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.thread_pool = QThreadPool()
        self.current_task = None

    def start_export(self, person_id=None):
        """Начинает процесс экспорта"""
        if self.current_task and not self.current_task.is_cancelled:
            return False

        self.current_task = ExportTask(self.db_manager, person_id)
        self.thread_pool.start(self.current_task)
        return True

    def cancel_export(self):
        """Отменяет текущий экспорт"""
        if self.current_task:
            self.current_task.cancel()
            self.current_task = None

    def is_exporting(self):
        """Проверяет, выполняется ли экспорт"""
        return (self.current_task is not None and 
                not self.current_task.is_cancelled and
                self.thread_pool.activeThreadCount() > 0)