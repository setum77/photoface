import os
import logging
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class ModelManager:
    """Класс для управления моделями InsightFace"""
    
    def __init__(self):
        self.models_dir = Path.home() / '.insightface' / 'models'
        self.available_models = {
            'buffalo_l': {
                'name': 'buffalo_l',
                'description': 'Сбалансированная модель с высокой точностью',
                'size_mb': 280,  # примерный размер
                'files': [
                    '1k3d68.onnx',
                    '2d106det.onnx',
                    'det_10g.onnx',
                    'genderage.onnx',
                    'w600k_r50.onnx'
                ]
            },
            'buffalo_s': {
                'name': 'buffalo_s',
                'description': 'Более быстрая, но менее точная модель',
                'size_mb': 360,  # примерный размер
                'files': [
                    '1k3d68.onnx',
                    '2d106det.onnx',
                    'det_500m.onnx',
                    'genderage.onnx',
                    'w600k_mbf.onnx'
                ]
            },
            'antelopev2': {
                'name': 'antelopev2',
                'description': 'Современная модель с улучшенной архитектурой',
                'size_mb': 130,  # примерный размер
                'files': [
                    '1k3d68.onnx',
                    '2d106det.onnx',
                    'glintr100.onnx',
                    'genderage.onnx',
                    'scrfd_10g_bnkps.onnx'
                ]
            }
        }
    
    def get_model_path(self, model_name: str) -> Path:
        """Получает путь к модели"""
        return self.models_dir / model_name
    
    def is_model_installed(self, model_name: str) -> bool:
        """Проверяет, установлена ли модель"""
        if model_name not in self.available_models:
            return False
            
        model_path = self.get_model_path(model_name)
        if not model_path.exists():
            return False
            
        model_info = self.available_models[model_name]
        
        # Для всех моделей проверяем файлы в основной папке
        for file_name in model_info['files']:
            file_path = model_path / file_name
            if not file_path.exists():
                logger.warning(f"Файл модели отсутствует: {file_path}")
                return False
                
        return True
    
    def get_available_models(self) -> List[str]:
        """Возвращает список доступных моделей"""
        return list(self.available_models.keys())
    
    def get_model_info(self, model_name: str) -> Dict:
        """Возвращает информацию о модели"""
        return self.available_models.get(model_name, {})
    
    def get_installed_models(self) -> List[str]:
        """Возвращает список установленных моделей"""
        installed = []
        for model_name in self.available_models:
            if self.is_model_installed(model_name):
                installed.append(model_name)
        return installed
    
    def get_model_size(self, model_name: str) -> int:
        """Возвращает примерный размер модели в МБ"""
        model_info = self.available_models.get(model_name, {})
        return model_info.get('size_mb', 0)
    
    def check_for_updates(self) -> Dict[str, bool]:
        """Проверяет, есть ли обновления для моделей"""
        # В текущей реализации мы не можем проверить версии моделей напрямую
        # через InsightFace API, поэтому возвращаем словарь с информацией о наличии моделей
        updates = {}
        for model_name in self.available_models:
            updates[model_name] = not self.is_model_installed(model_name)
        return updates
    
    def _extract_model_archive_properly(self, zip_path: Path, model_path: Path):
        """Распаковка: если файлы - в папку с именем архива, если папка - как есть."""
        archive_name = zip_path.stem  # имя архива без расширения
        temp_dir = Path(tempfile.mkdtemp())
        
        logger.info(f"Распаковка архива {zip_path} во временную папку {temp_dir}")
        
        with zipfile.ZipFile(zip_path, 'r') as zipref:
            zipref.extractall(temp_dir)
        
        # Получаем список содержимого временной папки
        temp_contents = list(temp_dir.iterdir())
        
        if len(temp_contents) == 1 and temp_contents[0].is_dir():
            # В архиве одна папка - распаковываем как есть
            folder_name = temp_contents[0].name
            logger.info(f"В архиве обнаружена папка: {folder_name}")
            
            # Создаем целевую папку, если не существует
            model_path.mkdir(parents=True, exist_ok=True)
            
            # Копируем все содержимое из временной папки в целевую
            for item in temp_contents[0].iterdir():
                dest = model_path / item.name
                if item.is_file():
                    shutil.copy2(str(item), str(dest))
                else:
                    shutil.copytree(str(item), str(dest))
            
            logger.info(f"Содержимое папки {folder_name} скопировано в {model_path}")
        else:
            # В архиве файлы на корневом уровне - создаем папку с именем архива
            logger.info("В архиве файлы на корневом уровне")
            
            # Создаем папку для модели
            model_path.mkdir(parents=True, exist_ok=True)
            
            # Копируем все файлы и папки в целевую папку
            for item in temp_contents:
                dest = model_path / item.name
                if item.is_file():
                    shutil.copy2(str(item), str(dest))
                else:
                    shutil.copytree(str(item), str(dest))
            
            logger.info(f"Файлы распакованы в папку {model_path}")
        
        # Удаляем временную папку
        shutil.rmtree(temp_dir)
        logger.info(f"Распаковка завершена в {model_path}")
    
    def _fix_model_structure(self, model_path: Path, model_name: str):
        """Финальная проверка и исправление структуры модели."""
        model_info = self.available_models.get(model_name, {})
        if 'files' not in model_info:
            return
        
        for filename in model_info['files']:
            expected_path = model_path / filename
            if not expected_path.exists():
                # Ищем в возможных вложенных папках
                for subdir in model_path.iterdir():
                    if subdir.is_dir():
                        candidate = subdir / filename
                        if candidate.exists():
                            shutil.move(str(candidate), str(expected_path))
                            logger.info(f"Перемещен {filename} из {subdir}")
                            break
    
    def download_model(self, model_name: str, progress_callback=None) -> bool:
        """Скачивает модель (вызывает InsightFace для загрузки)"""
        if model_name not in self.available_models:
            logger.error(f"Модель {model_name} не поддерживается")
            return False
            
        try:
            if progress_callback:
                progress_callback(0, "Начинаем загрузку модели...")
            
            # Проверим, существует ли архив модели для правильной распаковки
            model_path = self.get_model_path(model_name)
            zip_path = model_path.with_suffix('.zip')
            
            if zip_path.exists():
                # Распакуем архив правильно
                if progress_callback:
                    progress_callback(20, f"Подготовка распаковки {model_name}...")
                
                self._extract_model_archive_properly(zip_path, model_path)
                self._fix_model_structure(model_path, model_name)
                
                # После распаковки удалим архив, чтобы не мешал
                try:
                    os.remove(zip_path)
                    logger.info(f"Архив {zip_path.name} удален после распаковки")
                except Exception as e:
                    logger.warning(f"Не удалось удалить архив {zip_path.name}: {e}")
            
            import insightface
            from insightface.app import FaceAnalysis
            
            if progress_callback:
                progress_callback(50, f"Проверка файлов модели {model_name}...")
            
            # Проверим, что файлы модели действительно существуют
            # Но НЕ будем возвращать ошибку, если файлы отсутствуют, т.к. InsightFace сам их скачает
            model_info = self.available_models[model_name]
            missing_files = []
            
            for file_name in model_info['files']:
                file_path = model_path / file_name
                if not file_path.exists():
                    missing_files.append(file_name)
            
            if missing_files:
                logger.info(f"Файлы модели {model_name} отсутствуют, будет выполнена загрузка: {missing_files}")
            else:
                logger.info(f"Файлы модели {model_name} уже присутствуют в локальной папке")
            
            # Также проверим, есть ли файлы в подпапке (на случай, если распаковка не сработала правильно)
            if missing_files and model_path.exists():
                for subdir in model_path.iterdir():
                    if subdir.is_dir():
                        for file_name in missing_files[:]:  # Копируем список для итерации
                            nested_file_path = subdir / file_name
                            original_file_path = model_path / file_name
                            if nested_file_path.exists():
                                # Переместим файл из вложенной папки в основную
                                shutil.move(str(nested_file_path), str(original_file_path))
                                logger.info(f"Файл {file_name} перемещен из вложенной папки в основную")
                                # Уберем из списка отсутствующих
                                missing_files.remove(file_name)
            
            if progress_callback:
                progress_callback(70, f"Инициализация модели {model_name}...")
                
            # Пытаемся загрузить модель через InsightFace, который сам скачает при необходимости
            app = FaceAnalysis(name=model_name, providers=['CPUExecutionProvider'])
            
            if progress_callback:
                progress_callback(75, f"Загрузка модели {model_name} через InsightFace...")
                
            # Используем порог уверенности из настроек для фильтрации детекций
            min_confidence = 0.7  # значение по умолчанию
            # Попробуем получить доступ к конфигурации, если он доступен
            # В этом контексте у нас нет прямого доступа конфигурации,
            # но мы можем использовать значение по умолчанию, которое соответствует настройке
            app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=min_confidence)
            
            # После успешной загрузки проверим, какие файлы были скачаны и обновим статус
            model_info = self.available_models[model_name]
            downloaded_files = []
            missing_files = []
            
            for file_name in model_info['files']:
                file_path = model_path / file_name
                if file_path.exists():
                    downloaded_files.append(file_name)
                else:
                    missing_files.append(file_name)
            
            logger.info(f"Модель {model_name} - загружено файлов: {len(downloaded_files)}, отсутствует: {len(missing_files)}")
            
            if progress_callback:
                progress_callback(80, f"Подготовка модели {model_name}...")
            
            if progress_callback:
                progress_callback(100, f"Модель {model_name} успешно загружена!")
            
            logger.info(f"Модель {model_name} успешно загружена и готова к использованию")
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(-1, f"Ошибка загрузки модели: {str(e)}")
            logger.error(f"Ошибка при загрузке модели {model_name}: {e}")
            # Выводим более подробную информацию об ошибке
            import traceback
            logger.error(f"Трассировка ошибки: {traceback.format_exc()}")
            return False
    
    def get_model_download_status(self, model_name: str) -> Tuple[bool, str]:
        """Проверяет статус загрузки модели"""
        if model_name not in self.available_models:
            return False, f"Модель {model_name} не поддерживается"
            
        model_path = self.get_model_path(model_name)
        
        if not model_path.exists():
            return False, f"Модель {model_name} не загружена"
        
        model_info = self.available_models[model_name]
        missing_files = []
        
        # Для всех моделей проверяем файлы в основной папке
        for file_name in model_info['files']:
            file_path = model_path / file_name
            if not file_path.exists():
                missing_files.append(file_name)
        
        if missing_files:
            return False, f"Отсутствуют файлы: {', '.join(missing_files)}"
        
        return True, f"Модель {model_name} полностью загружена"
    
    def validate_model_files(self, model_name: str) -> bool:
        """Проверяет целостность файлов модели"""
        try:
            import insightface
            from insightface.app import FaceAnalysis
            
            # Пытаемся инициализировать модель для проверки целостности
            app = FaceAnalysis(name=model_name, providers=['CPUExecutionProvider'])
            # Используем порог уверенности из настроек для фильтрации детекций
            min_confidence = 0.7  # значение по умолчанию
            app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=min_confidence)
            
            logger.info(f"Модель {model_name} прошла проверку целостности")
            return True
            
        except Exception as e:
            logger.error(f"Модель {model_name} не прошла проверку целостности: {e}")
            return False