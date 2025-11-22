import os
import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class FaceAnalyzer:
    def __init__(self):
        self.model = None
        self.initialized = False
        
    def initialize(self):
        """Инициализация модели распознавания лиц"""
        if self.initialized:
            logger.debug("Модель уже инициализирована")
            return True
        
        try:
            logger.info("Инициализация модели распознавания лиц...")
            
            # Создаем экземпляр FaceAnalysis
            self.model = FaceAnalysis(
                name='buffalo_l',  # Модель по умолчанию
                providers=['CPUExecutionProvider']  # Используем CPU для совместимости
            )
            
            # Подготовка модели
            self.model.prepare(ctx_id=0, det_size=(640, 640))
            
            self.initialized = True
            logger.info("Модель распознавания лиц успешно инициализирована")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации модели распознавания лиц: {e}")
            self.initialized = False
            return False

    def detect_faces(self, image_path):
        """
        Обнаруживает лица на изображении и возвращает информацию о них
        """
        if not self.initialized:
            if not self.initialize():
                return []

        try:
            logger.debug(f"Начинаем детекцию лиц в: {image_path}")
            
            if not os.path.exists(image_path):
                logger.error(f"Файл не существует: {image_path}")
                return []
                
            # Загружаем изображение с помощью OpenCV
            img = cv2.imread(image_path)
            
            if img is None:
                logger.error(f"OpenCV не смог загрузить изображение: {image_path}")
                try:
                    from PIL import Image as PILImage
                    pil_img = PILImage.open(image_path)
                    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                    logger.info(f"Успешно загружено через PIL: {image_path}")
                except Exception as pil_error:
                    logger.error(f"PIL тоже не смог загрузить: {image_path}, ошибка: {pil_error}")
                    return []
            
            if img is None:
                logger.error(f"Не удалось загрузить изображение никаким методом: {image_path}")
                return []

            height, width = img.shape[:2]
            logger.debug(f"Изображение загружено, размер: {width}x{height}")
            
            # Конвертируем BGR в RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Детекция лиц
            logger.debug("Выполняем детекцию лиц...")
            faces = self.model.get(img_rgb)
            logger.debug(f"Модель вернула {len(faces)} лиц")
            
            results = []
            for i, face in enumerate(faces):
                # Получаем bounding box - ВАЖНО: убедимся в правильности координат
                bbox = face.bbox.astype(float)  # Используем float для точности
                
                # InsightFace может возвращать координаты в разных форматах
                # Проверим и нормализуем координаты
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                else:
                    logger.warning(f"Некорректный формат bbox: {bbox}")
                    continue
                
                # Убедимся, что координаты в пределах изображения
                x1 = max(0, float(x1))
                y1 = max(0, float(y1))
                x2 = min(width, float(x2))
                y2 = min(height, float(y2))
                
                # Проверяем валидность bbox
                if x1 >= x2 or y1 >= y2:
                    logger.warning(f"Некорректный bbox: ({x1}, {y1}, {x2}, {y2})")
                    continue
                
                # Логируем для отладки
                logger.debug(f"Лицо {i+1}: bbox=({x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f}), "
                            f"размер=({x2-x1:.1f}x{y2-y1:.1f}), confidence={face.det_score:.3f}")
                
                results.append({
                    'bbox': (x1, y1, x2, y2),
                    'embedding': face.embedding.tobytes(),
                    'confidence': float(face.det_score),
                    'landmarks': face.kps if hasattr(face, 'kps') else None
                })
                
            logger.info(f"Найдено {len(results)} лиц в {os.path.basename(image_path)}")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка при обработке изображения {image_path}: {e}")
            import traceback
            logger.error(f"Трассировка: {traceback.format_exc()}")
            return []

    def calculate_similarity(self, embedding1, embedding2):
        """
        Вычисляет схожесть между двумя эмбеддингами
        
        Args:
            embedding1: Первый эмбеддинг (bytes или numpy array)
            embedding2: Второй эмбеддинг (bytes или numpy array)
            
        Returns:
            float: Коэффициент схожести (0-1)
        """
        try:
            # Конвертируем bytes в numpy array если нужно
            if isinstance(embedding1, bytes):
                emb1 = np.frombuffer(embedding1, dtype=np.float32)
            else:
                emb1 = embedding1
                
            if isinstance(embedding2, bytes):
                emb2 = np.frombuffer(embedding2, dtype=np.float32)
            else:
                emb2 = embedding2
                
            # Нормализуем векторы
            emb1 = emb1 / np.linalg.norm(emb1)
            emb2 = emb2 / np.linalg.norm(emb2)
            
            # Вычисляем косинусное сходство
            similarity = np.dot(emb1, emb2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Ошибка вычисления схожести: {e}")
            return 0.0

    def draw_faces_on_image(self, image_path, faces_info, output_path=None):
        """
        Рисует рамки вокруг лиц на изображении
        
        Args:
            image_path: Путь к исходному изображению
            faces_info: Список информации о лицах
            output_path: Путь для сохранения результата (опционально)
            
        Returns:
            PIL.Image: Изображение с нарисованными рамками
        """
        try:
            # Загружаем изображение
            image = Image.open(image_path)
            img_cv = cv2.imread(image_path)
            
            # Рисуем рамки для каждого лица
            for face in faces_info:
                bbox = face['bbox']
                confidence = face['confidence']
                
                # Рисуем прямоугольник
                color = (0, 255, 0)  # Зеленый цвет
                thickness = 2
                cv2.rectangle(img_cv, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, thickness)
                
                # Добавляем текст с confidence
                text = f"{confidence:.2f}"
                font_scale = 0.7
                cv2.putText(img_cv, text, (bbox[0], bbox[1]-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            
            # Конвертируем обратно в PIL Image
            img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
            result_image = Image.fromarray(img_rgb)
            
            # Сохраняем если указан output_path
            if output_path:
                result_image.save(output_path)
                
            return result_image
            
        except Exception as e:
            logger.error(f"Ошибка при рисовании рамок: {e}")
            return None
    
    def check_image_support(self, image_path):
        """Проверяет, поддерживается ли формат изображения"""
        try:
            from PIL import Image as PILImage
            with PILImage.open(image_path) as img:
                format = img.format
                mode = img.mode
                size = img.size
                logger.info(f"Формат: {format}, режим: {mode}, размер: {size}")
                return True
        except Exception as e:
            logger.error(f"Изображение не поддерживается: {image_path}, ошибка: {e}")
            return False
        
    # Диагностический метод!!!
    def test_face_detection_with_debug(self, image_path):
        """Тестовая детекция с подробной отладочной информацией"""
        if not self.initialized:
            if not self.initialize():
                return []
        
        try:
            print(f"=== ТЕСТ ДЕТЕКЦИИ ДЛЯ {image_path} ===")
            
            # Загружаем изображение
            img = cv2.imread(image_path)
            if img is None:
                print("Ошибка: не удалось загрузить изображение")
                return []
            
            height, width = img.shape[:2]
            print(f"Размер изображения: {width}x{height}")
            
            # Конвертируем в RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Детекция лиц
            faces = self.model.get(img_rgb)
            print(f"Найдено лиц моделью: {len(faces)}")
            
            results = []
            for i, face in enumerate(faces):
                bbox = face.bbox.astype(int)
                x1, y1, x2, y2 = bbox
                
                print(f"Лицо {i+1}:")
                print(f"  Исходный bbox: {bbox}")
                print(f"  Координаты: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
                print(f"  Размер области: {x2-x1}x{y2-y1}")
                print(f"  Confidence: {face.det_score:.3f}")
                
                # Проверяем границы
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(width, x2)
                y2 = min(height, y2)
                
                print(f"  После коррекции границ: ({x1}, {y1}, {x2}, {y2})")
                
                results.append({
                    'bbox': (x1, y1, x2, y2),
                    'embedding': face.embedding.tobytes(),
                    'confidence': float(face.det_score)
                })
            
            return results
            
        except Exception as e:
            print(f"Ошибка в тестовой детекции: {e}")
            import traceback
            print(f"Трассировка: {traceback.format_exc()}")
            return []