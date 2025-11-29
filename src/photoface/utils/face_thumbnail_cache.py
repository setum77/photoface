import os
import hashlib
from typing import Dict, Optional, Tuple
from PIL import Image
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QBuffer, QIODevice
from src.photoface.utils.helpers import pil_to_pixmap

class FaceThumbnailCache:
    """Класс для кэширования миниатюр лиц с поддержкой персистентности в БД"""
    
    def __init__(self, db_manager=None, cache_size: int = 1000):
        self.db_manager = db_manager
        self.cache_size = cache_size
        self.cache: Dict[str, QPixmap] = {}  # Кэш в памяти
        self.cache_order: list = []  # Для LRU кэширования
        self.cache_keys_map: Dict[str, int] = {}  # Сопоставление ключа кэша и face_id
    
    def _generate_cache_key(self, image_path: str, bbox: Tuple[float, float, float, float]) -> str:
        """Генерирует уникальный ключ для кэширования миниатюры"""
        bbox_str = f"{bbox[0]:.2f}_{bbox[1]:.2f}_{bbox[2]:.2f}_{bbox[3]:.2f}"
        path_hash = hashlib.md5(image_path.encode()).hexdigest()
        return f"{path_hash}_{bbox_str}"
    
    def _pixmap_to_bytes(self, pixmap: QPixmap) -> bytes:
        """Конвертирует QPixmap в байты для сохранения в БД"""
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")  # Используем PNG для лучшего качества
        return buffer.data()
    
    def _bytes_to_pixmap(self, data: bytes) -> Optional[QPixmap]:
        """Конвертирует байты из БД в QPixmap"""
        if not data:
            return None
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            return pixmap
        return None
    
    def _load_and_crop_thumbnail(self, image_path: str, bbox: Tuple[float, float, float, float], size: Tuple[int, int] = (120, 120)) -> Optional[QPixmap]:
        """Загружает изображение, обрезает лицо и создает миниатюру"""
        try:
            with Image.open(image_path) as orig_img:
                # Получаем координаты области лица
                x1, y1, x2, y2 = bbox

                # Убедимся, что координаты - числа
                x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
                
                # Обрезаем область лица из оригинального изображения
                face_crop = orig_img.crop((int(x1), int(y1), int(x2), int(y2)))
                
                # Масштабируем до размера миниатюры
                face_thumb = face_crop.resize(size)
                
                pixmap = pil_to_pixmap(face_thumb)
                return pixmap
        except Exception as e:
            print(f"Ошибка загрузки миниатюры лица: {e}")
            import traceback
            print(f"Трассировка: {traceback.format_exc()}")
            return None
    
    def get_thumbnail(self, face_id: int, image_path: str, bbox: Tuple[float, float, float, float], size: Tuple[int, int] = (120, 120)) -> Optional[QPixmap]:
        """Получает миниатюру из кэша (память или БД) или создает новую"""
        cache_key = self._generate_cache_key(image_path, bbox)
        
        # Проверяем наличие в кэше в памяти
        if cache_key in self.cache:
            # Обновляем порядок использования (LRU)
            self.cache_order.remove(cache_key)
            self.cache_order.append(cache_key)
            return self.cache[cache_key]
        
        # Проверяем наличие в БД если db_manager доступен
        pixmap = None
        if self.db_manager:
            thumbnail_data = self.db_manager.get_face_thumbnail(face_id)
            if thumbnail_data:
                pixmap = self._bytes_to_pixmap(thumbnail_data)
                if pixmap:
                    # Добавляем в кэш в памяти
                    self._add_to_cache(cache_key, pixmap, face_id)
                    return pixmap
        
        # Создаем новую миниатюру
        pixmap = self._load_and_crop_thumbnail(image_path, bbox, size)
        
        if pixmap and self.db_manager:
            # Сохраняем в БД
            thumbnail_data = self._pixmap_to_bytes(pixmap)
            self.db_manager.save_face_thumbnail(face_id, thumbnail_data)
        
        if pixmap:
            # Добавляем в кэш в памяти
            self._add_to_cache(cache_key, pixmap, face_id)
        
        return pixmap
    
    def _add_to_cache(self, cache_key: str, pixmap: QPixmap, face_id: int):
        """Добавляет миниатюру в кэш с учетом ограничения размера"""
        if cache_key in self.cache:
            # Удаляем старый ключ из порядка
            self.cache_order.remove(cache_key)
        elif len(self.cache) >= self.cache_size:
            # Удаляем лишние элементы если превышен размер кэша
            oldest_key = self.cache_order.pop(0)
            del self.cache[oldest_key]
            if oldest_key in self.cache_keys_map:
                del self.cache_keys_map[oldest_key]
        
        # Добавляем новый ключ в конец
        self.cache_order.append(cache_key)
        self.cache[cache_key] = pixmap
        self.cache_keys_map[cache_key] = face_id
    
    def clear_cache(self):
        """Очищает кэш в памяти"""
        self.cache.clear()
        self.cache_order.clear()
        self.cache_keys_map.clear()
    
    def get_cache_stats(self) -> Tuple[int, int]:
        """Возвращает статистику кэша (размер, максимальный размер)"""
        return len(self.cache), self.cache_size
    
    def performance_test(self, test_face_id: int, test_image_path: str, test_bbox: Tuple[float, float, float], iterations: int = 100):
        """Тестирует производительность кэширования"""
        import time
        
        # Тестируем загрузку без кэширования (первый вызов)
        start_time = time.time()
        pixmap = self._load_and_crop_thumbnail(test_image_path, test_bbox)
        first_load_time = time.time() - start_time
        
        # Тестируем загрузку с кэшированием (второй и последующие вызовы)
        start_time = time.time()
        for _ in range(iterations):
            pixmap = self.get_thumbnail(test_face_id, test_image_path, test_bbox)
        cached_load_time = time.time() - start_time
        
        # Рассчитываем среднее время для кэшированной загрузки
        avg_cached_time = cached_load_time / iterations if iterations > 0 else 0
        
        return {
            'first_load_time': first_load_time,
            'cached_load_time': cached_load_time,
            'avg_cached_time': avg_cached_time,
            'iterations': iterations,
            'improvement_factor': first_load_time / avg_cached_time if avg_cached_time > 0 else float('inf')
        }