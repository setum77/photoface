import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Config:
    """Класс для управления настройками приложения"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self.get_default_config_path()
        self.settings = self.load_settings()
        
    def get_default_config_path(self) -> str:
        """Возвращает путь к файлу конфигурации по умолчанию"""
        config_dir = Path.home() / '.photoface'
        config_dir.mkdir(exist_ok=True)
        return str(config_dir / 'config.json')
    
    def load_settings(self) -> Dict[str, Any]:
        """Загружает настройки из файла"""
        default_settings = {
            'ui': {
                'window_geometry': None,
                'window_state': None,
                'splitter_sizes': [300, 900],
                'last_tab_index': 0
            },
            'scan': {
                'similarity_threshold': 0.6,
                'min_face_confidence': 0.7,
                'auto_cluster_after_scan': True
            },
            'export': {
                'last_output_path': '',
                'create_info_files': True,
                'preserve_folder_structure': False
            },
            'editor': {
                'external_editor_path': '',
                'open_after_edit': True
            },
            'performance': {
                'max_threads': 4,
                'thumbnail_size': 200,
                'cache_thumbnails': True
            }
        }
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Объединяем с настройками по умолчанию
                    self.merge_dicts(default_settings, loaded_settings)
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек: {e}")
            
        return default_settings
    
    def merge_dicts(self, target: Dict, source: Dict):
        """Рекурсивно объединяет словари"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self.merge_dicts(target[key], value)
            else:
                target[key] = value
    
    def save_settings(self):
        """Сохраняет настройки в файл"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}")
    
    def get(self, key: str, default=None) -> Any:
        """Получает значение настройки по ключу"""
        keys = key.split('.')
        value = self.settings
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """Устанавливает значение настройки"""
        keys = key.split('.')
        settings = self.settings
        
        for k in keys[:-1]:
            if k not in settings or not isinstance(settings[k], dict):
                settings[k] = {}
            settings = settings[k]
        
        settings[keys[-1]] = value
        self.save_settings()
    
    def get_external_editor_path(self) -> str:
        """Возвращает путь к внешнему редактору"""
        return self.get('editor.external_editor_path', '')
    
    def set_external_editor_path(self, path: str):
        """Устанавливает путь к внешнему редактору"""
        self.set('editor.external_editor_path', path)
    
    def get_last_output_path(self) -> str:
        """Возвращает последний путь экспорта"""
        return self.get('export.last_output_path', '')
    
    def set_last_output_path(self, path: str):
        """Устанавливает последний путь экспорта"""
        self.set('export.last_output_path', path)