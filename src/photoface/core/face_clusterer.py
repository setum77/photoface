import numpy as np
import logging
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Tuple, Dict, Any
import sqlite3

logger = logging.getLogger(__name__)

class FaceClusterer:
    """Класс для кластеризации лиц на основе эмбеддингов
    
    Кластеризация зависит от выбранной модели InsightFace, так как разные модели
    генерируют разные векторы эмбеддингов для одного и того же лица. Рекомендуется
    использовать одну и ту же модель для детекции и кластеризации на всем протяжении
    обработки изображений.
    """
    
    def __init__(self, db_manager, similarity_threshold=0.6, config=None):
        self.db_manager = db_manager
        self.similarity_threshold = similarity_threshold
        self.config = config
    
    def _get_next_cluster_id(self):
        """Получает следующий ID кластера с ведущими нулями"""
        # Получаем общее количество всех лиц в базе данных (всех записей в таблице faces)
        # которое используется для определения количества цифр в номере
        total_faces = self.db_manager.get_total_faces_count()
        
        # Получаем последний использованный cluster_id из настроек
        last_cluster_id = self.db_manager.get_setting('last_cluster_id', '0')
        try:
            last_cluster_id = int(last_cluster_id)
        except ValueError:
            last_cluster_id = 0
        
        # Вычисляем следующий ID (первый номер начинается с 1)
        next_cluster_id = last_cluster_id + 1
        
        # Определяем количество цифр в номере в зависимости от общего количества кластеров
        # В задании сказано, что если количество расспознаных лиц двухзначное,
        # то {cluster_id} будет двухзначный и т.д.
        if total_faces < 10:
            digits = 1
        elif total_faces < 100:
            digits = 2
        elif total_faces < 1000:
            digits = 3
        elif total_faces < 10000:
            digits = 4
        else:
            digits = 5  # Для очень большого количества лиц
        
        # Форматируем ID с ведущими нулями
        formatted_id = str(next_cluster_id).zfill(digits)
        
        # Сохраняем новый последний ID в настройках
        self.db_manager.set_setting('last_cluster_id', str(next_cluster_id))
        
        return formatted_id
        
    def cluster_faces(self) -> Dict[int, List[int]]:
        """
        Выполняет кластеризацию нераспознанных лиц
        
        Returns:
            Dict[int, List[int]]: Словарь {cluster_id: [face_ids]}
        """
        try:
            # Логирование параметров кластеризации
            model_name = self.config.get('scan.face_model_name', 'unknown') if self.config else 'unknown'
            threshold = self.config.get('scan.similarity_threshold', self.similarity_threshold) if self.config else self.similarity_threshold
            min_confidence = self.config.get('scan.min_face_confidence', 'unknown') if self.config else 'unknown'
            
            logger.info(f"Начало кластеризации лиц")
            logger.info(f"Модель: {model_name}")
            logger.info(f"Порог схожести: {threshold}")
            logger.info(f"Минимальная уверенность лица: {min_confidence}")
            
            # Получаем все нераспознанные эмбеддинги
            face_data = self.db_manager.get_all_face_embeddings()
            
            if not face_data:
                logger.info("Нет нераспознанных лиц для кластеризации")
                return {}
            
            face_ids = []
            embeddings = []
            
            for face_id, embedding_bytes, _, _ in face_data:  # Обновляем, чтобы получить is_person
                if embedding_bytes:
                    embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                    face_ids.append(face_id)
                    embeddings.append(embedding)
            
            if len(embeddings) < 2:
                logger.info("Недостаточно лиц для кластеризации")
                return {}
            
            # Создаем массив сырых эмбеддингов
            embeddings_array = np.array(embeddings)

            # Применяем предложенные улучшения
            embeddings_array = np.nan_to_num(embeddings_array, nan=0.0, posinf=0.0, neginf=0.0)
            norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
            norms[norms == 0] = 1  # Избежать /0
            embeddings_array /= norms
            
            similarity_matrix = cosine_similarity(embeddings_array)
            similarity_matrix = np.clip(similarity_matrix, -1, 1)  # Clamp
            distance_matrix = 1 - similarity_matrix # Теперь >=0
            
            # Используем DBSCAN для кластеризации
            clustering = DBSCAN(
                eps=1 - threshold,
                min_samples=2,  # Теперь кластер формируется только если в нем 2 или более лиц
                metric='precomputed'
            )
            
            clusters = clustering.fit_predict(distance_matrix)
            
            # Группируем лица по кластерам
            cluster_groups = {}
            for face_id, cluster_id in zip(face_ids, clusters):
                if cluster_id == -1:
                    # Шум - не группируем, оставляем как отдельные лица в "not recognized"
                    continue # Пропускаем шумовые точки
                
                if cluster_id not in cluster_groups:
                    cluster_groups[cluster_id] = []
                cluster_groups[cluster_id].append(face_id)
            
            logger.info(f"Создано {len(cluster_groups)} кластеров из {len(face_ids)} лиц")
            return cluster_groups
        except Exception as e:
            logger.error(f"Ошибка при кластеризации лиц: {e}")
            return {}
    
    def apply_clusters_to_database(self, cluster_groups: Dict[int, List[int]]):
        """
        Применяет результаты кластеризации к базе данных
        Создает новых персон для каждого кластера
        """
        try:
            created_persons = 0
            
            for cluster_id, face_ids in cluster_groups.items():
                if len(face_ids) < 1:
                    continue
                
                # Создаем новую персону для кластера с использованием нового формата имени
                formatted_cluster_id = self._get_next_cluster_id()
                person_name = f"Person_{formatted_cluster_id}"
                person_id = self.db_manager.create_person(person_name)
                
                if person_id:
                    # Перемещаем все лица кластера к новой персоне
                    for face_id in face_ids:
                        self.db_manager.move_face_to_person(face_id, person_id)
                        # Устанавливаем is_person = 0, так как это автоматически сгруппированные лица
                        self.db_manager.set_face_person_status(face_id, 0)
                    created_persons += 1
            
            logger.info(f"Создано {created_persons} новых персон из кластеров")
            return created_persons
            
        except Exception as e:
            logger.error(f"Ошибка применения кластеров к БД: {e}")
            return 0
    
    def find_similar_faces(self, face_id, threshold=None):
        """
        Находит похожие лица для заданного лица
        """
        if threshold is None:
            threshold = self.config.get('scan.similarity_threshold', self.similarity_threshold) if self.config else self.similarity_threshold
            
        try:
            # Получаем эмбеддинг целевого лица
            target_embedding_bytes = self.db_manager.get_face_embedding(face_id)
            if not target_embedding_bytes:
                return []
            
            target_embedding = np.frombuffer(target_embedding_bytes, dtype=np.float32)
            target_embedding_norm = target_embedding / np.linalg.norm(target_embedding)
            
            # Получаем все эмбеддинги
            face_data = self.db_manager.get_all_face_embeddings()
            
            similar_faces = []
            for other_face_id, other_embedding_bytes, person_name in face_data:
                if other_face_id == face_id or not other_embedding_bytes:
                    continue
                
                other_embedding = np.frombuffer(other_embedding_bytes, dtype=np.float32)
                other_embedding_norm = other_embedding / np.linalg.norm(other_embedding)
                
                # Вычисляем схожесть
                similarity = np.dot(target_embedding_norm, other_embedding_norm)
                
                if similarity >= threshold:
                    similar_faces.append({
                        'face_id': other_face_id,
                        'similarity': similarity,
                        'person_name': person_name
                    })
            
            # Сортируем по убыванию схожести
            similar_faces.sort(key=lambda x: x['similarity'], reverse=True)
            return similar_faces
            
        except Exception as e:
            logger.error(f"Ошибка поиска похожих лиц: {e}")
            return []
    
    def test_cluster_naming(self):
        """Тестирование логики именования кластеров"""
        # Тестируем несколько сценариев
        print("Тестирование логики именования кластеров:")
        
        # Предположим, что в системе 5 кластеров (однозначное число)
        # Подделываем метод get_total_faces_count, чтобы вернуть 5
        original_get_total = self.db_manager.get_total_faces_count
        self.db_manager.get_total_faces_count = lambda: 5
        
        # Сбрасываем последний кластер ID в настройках
        self.db_manager.set_setting('last_cluster_id', '0')
        
        # Генерируем несколько кластеров
        for i in range(1, 6):
            cluster_id = self._get_next_cluster_id()
            print(f"Кластер {i}: {cluster_id} (ожидаем однозначный формат)")
        
        # Предположим, что в системе 45 кластеров (двухзначное число)
        self.db_manager.get_total_faces_count = lambda: 45
        
        # Генерируем еще несколько кластеров
        for i in range(6, 11):
            cluster_id = self._get_next_cluster_id()
            print(f"Кластер {i}: {cluster_id} (ожидаем двузначный формат)")
        
        # Восстанавливаем оригинальный метод
        self.db_manager.get_total_faces_count = original_get_total