import os
import logging
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
                'size_mb': 400,  # примерный размер
                'files': [
                    '1k3d68.onnx',
                    '2d106det.onnx',
                    'det_10g.onnx',
                    'genderage.onnx',
                    'w600k_r50.onnx'
                ]
            },
            'antelopev2': {
                'name': 'antelopev2',
                'description': 'Современная модель с улучшенной архитектурой',
                'size_mb': 400,  # примерный размер
                'files': [
                    '1k3d68.onnx',
                    '2d106det.onnx',
                    'det_10g.onnx',
                    'genderage.onnx',
                    'w600k_r50.onnx'
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
    
    def download_model(self, model_name: str, progress_callback=None) -> bool:
        """Скачивает модель (вызывает InsightFace для загрузки)"""
        if model_name not in self.available_models:
            logger.error(f"Модель {model_name} не поддерживается")
            return False
            
        try:
            if progress_callback:
                progress_callback(0, "Начинаем загрузку модели...")
            
            import insightface
            from insightface.app import FaceAnalysis
            
            # Создаем экземпляр FaceAnalysis с указанной моделью
            # Это автоматически загрузит модель, если она отсутствует
            if progress_callback:
                progress_callback(30, f"Инициализация модели {model_name}...")
                
            app = FaceAnalysis(name=model_name, providers=['CPUExecutionProvider'])
            
            if progress_callback:
                progress_callback(60, f"Подготовка модели {model_name}...")
                
            app.prepare(ctx_id=0, det_size=(640, 640))
            
            # Для antelopev2 может потребоваться дополнительная обработка
            # из-за структуры папок в архиве
            if model_name == 'antelopev2':
                if progress_callback:
                    progress_callback(80, "Корректировка структуры папок antelopev2...")
                self.fix_antelope2_structure(model_name)
            
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
            logger.error(f"Трессировка ошибки: {traceback.format_exc()}")
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
            app.prepare(ctx_id=0, det_size=(640, 640))
            
            logger.info(f"Модель {model_name} прошла проверку целостности")
            return True
            
        except Exception as e:
            logger.error(f"Модель {model_name} не прошла проверку целостности: {e}")
            return False
    
    # Метод fix_antelope2_structure больше не нужен, так как правильная распаковка
    # теперь происходит при первоначальной загрузке модели
    
    def _extract_antelopev2_properly(self, zip_path, model_path):
        """Правильно распаковывает архив antelopev2, избегая создания папки в папке"""
        import zipfile
        import tempfile
        import shutil
        
        try:
            # Создаем временный каталог для распаковки
            with tempfile.TemporaryDirectory() as temp_dir:
                # Распаковываем архив во временный каталог
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Находим внутреннюю папку antelopev2 (если она есть)
                temp_contents = list(Path(temp_dir).iterdir())
                
                # Если внутри один каталог с именем antelopev2, используем его содержимое
                if len(temp_contents) == 1 and temp_contents[0].is_dir() and temp_contents[0].name == 'antelopev2':
                    inner_folder = temp_contents[0]
                    # Копируем содержимое внутренней папки в целевую папку
                    for item in inner_folder.iterdir():
                        dest_path = model_path / item.name
                        if item.is_file():
                            shutil.copy2(str(item), str(dest_path))
                        else:
                            shutil.copytree(str(item), str(dest_path))
                else:
                    # Если структура другая, копируем все содержимое
                    for item in Path(temp_dir).iterdir():
                        dest_path = model_path / item.name
                        if item.is_file():
                            shutil.copy2(str(item), str(dest_path))
                        else:
                            shutil.copytree(str(item), str(dest_path))
                            
            logger.info("Antelopev2 архив распакован корректно")
        except Exception as e:
            logger.error(f"Ошибка при распаковке antelopev2: {e}")
            raise
    
    def download_model(self, model_name: str, progress_callback=None) -> bool:
        """Скачивает модель (вызывает InsightFace для загрузки)"""
        if model_name not in self.available_models:
            logger.error(f"Модель {model_name} не поддерживается")
            return False
            
        try:
            if progress_callback:
                progress_callback(0, "Начинаем загрузку модели...")
            
            # Для antelopev2 сначала проверим, нужно ли выполнить правильную распаковку
            if model_name == 'antelopev2':
                # Проверим, существует ли архив
                import os
                model_path = self.get_model_path(model_name)
                zip_path = model_path.with_suffix('.zip')
                
                if zip_path.exists():
                    # Распакуем архив правильно: содержимое из внутренней папки переместим в основную
                    if progress_callback:
                        progress_callback(20, "Подготовка распаковки antelopev2...")
                    self._extract_antelopev2_properly(zip_path, model_path)
            
            import insightface
            from insightface.app import FaceAnalysis
            
            if progress_callback:
                progress_callback(40, f"Инициализация модели {model_name}...")
                
            # Создаем экземпляр FaceAnalysis с указанной моделью
            # Это автоматически загрузит модель, если она отсутствует
            app = FaceAnalysis(name=model_name, providers=['CPUExecutionProvider'])
            
            if progress_callback:
                progress_callback(70, f"Подготовка модели {model_name}...")
                
            app.prepare(ctx_id=0, det_size=(640, 640))
            
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
            logger.error(f"Трессировка ошибки: {traceback.format_exc()}")
            return False