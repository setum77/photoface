import os
import json
import logging
from typing import Dict, Any, Optional
from .database import DatabaseManager

logger = logging.getLogger(__name__)

class Config:
    """Класс для управления настройками приложения"""
    
    def __init__(self, db_manager: DatabaseManager = None, config_path: str = None):
        # Если передан DatabaseManager, используем его, иначе создаем новый
        # config_path теперь не используется, так как настройки хранятся в базе данных
        self.db_manager = db_manager
        self.settings = self.load_settings()
        
    def load_settings(self) -> Dict[str, Any]:
        """Загружает настройки из базы данных"""
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
                'auto_cluster_after_scan': True,
                'face_model_name': 'buffalo_l'  # Новая настройка для выбора модели
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
        
        if self.db_manager:
            try:
                # Получаем все настройки из базы данных
                db_settings = self.db_manager.get_all_settings()
                
                # Десериализуем JSON-значения и объединяем с настройками по умолчанию
                for key, value in db_settings.items():
                    deserialized_value = self._deserialize_value(value)
                    
                    # Разбиваем ключ на части (например, 'ui.window_geometry')
                    keys = key.split('.')
                    current_dict = default_settings
                    
                    # Проходим по всем частям ключа, кроме последней
                    for k in keys[:-1]:
                        if k not in current_dict or not isinstance(current_dict[k], dict):
                            current_dict[k] = {}
                        current_dict = current_dict[k]
                    
                    # Устанавливаем значение для последнего ключа
                    current_dict[keys[-1]] = deserialized_value
            except Exception as e:
                logger.error(f"Ошибка загрузки настроек из базы данных: {e}")
        else:
            logger.warning("Database manager not provided, using default settings")
            
        return default_settings
    
    
    def save_settings(self):
        """Сохраняет настройки в базу данных"""
        if self.db_manager:
            try:
                # Рекурсивно сохраняем все настройки в базу данных
                self._save_dict_to_db('', self.settings)
            except Exception as e:
                logger.error(f"Ошибка сохранения настроек в базу данных: {e}")
        else:
            logger.warning("Database manager not provided, cannot save settings")

    def _save_dict_to_db(self, prefix: str, data: Dict):
        """Рекурсивно сохраняет словарь в базу данных"""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                # Если значение - словарь, рекурсивно сохраняем его
                self._save_dict_to_db(full_key, value)
            else:
                # Если значение - примитив, сохраняем в базу данных как JSON
                json_value = self._serialize_value(value)
                self.db_manager.set_setting(full_key, json_value)

    def _serialize_value(self, value):
        """Сериализует значение для сохранения в базе данных"""
        try:
            # Попробуем обычную сериализацию JSON
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            # Обработка специфичных PyQt типов
            try:
                # Для QByteArray (например, геометрия окна)
                if hasattr(value, 'data') and callable(getattr(value, 'data')):
                    try:
                        # QByteArray может быть преобразован в байты, затем в hex строку
                        byte_data = value.data()
                        import base64
                        encoded = base64.b64encode(byte_data).decode('ascii')
                        return json.dumps({"__type__": "QByteArray", "__value__": encoded}, ensure_ascii=False)
                    except:
                        # Если не получилось, конвертируем в строку
                        return json.dumps(str(value), ensure_ascii=False)
                
                # Добавим другие специфичные типы при необходимости
                return json.dumps(str(value), ensure_ascii=False)
            except:
                # Если ничего не помогает, сохраняем как строку
                return json.dumps(str(value), ensure_ascii=False)

    def _deserialize_value(self, value_str):
        """Десериализует значение из базы данных"""
        try:
            parsed = json.loads(value_str)
            # Проверим, является ли это специальным типом
            if isinstance(parsed, dict) and parsed.get("__type__") == "QByteArray":
                import base64
                encoded = parsed["__value__"]
                byte_data = base64.b64decode(encoded.encode('ascii'))
                # Возвращаем как есть, так как мы не можем воссоздать оригинальный PyQt объект
                # в простой строке для сохранения совместимости
                return byte_data
            return parsed
        except json.JSONDecodeError:
            # Если не JSON, возвращаем как строку
            return value_str
    
    def get(self, key: str, default=None) -> Any:
        """Получает значение настройки по ключу"""
        keys = key.split('.')
        value = self.settings
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # Если не найдено в локальных настройках, пробуем получить из базы данных
                if self.db_manager:
                    try:
                        db_value = self.db_manager.get_setting(key)
                        if db_value is not None:
                            return self._deserialize_value(db_value)
                    except Exception:
                        pass
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
        
        # Также сохраняем в базу данных немедленно, если доступен db_manager
        if self.db_manager:
            json_value = self._serialize_value(value)
            self.db_manager.set_setting(key, json_value)
    
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