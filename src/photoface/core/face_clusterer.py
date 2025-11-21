import numpy as np
import logging
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Tuple, Dict, Any
import sqlite3

logger = logging.getLogger(__name__)

class FaceClusterer:
    """Класс для кластеризации лиц на основе эмбеддингов"""
    
    def __init__(self, db_manager, similarity_threshold=0.6):
        self.db_manager = db_manager
        self.similarity_threshold = similarity_threshold
        
    def cluster_faces(self) -> Dict[int, List[int]]:
        """
        Выполняет кластеризацию нераспознанных лиц
        
        Returns:
            Dict[int, List[int]]: Словарь {cluster_id: [face_ids]}
        """
        try:
            # Получаем все нераспознанные эмбеддинги
            face_data = self.db_manager.get_all_face_embeddings()
            
            if not face_data:
                logger.info("Нет нераспознанных лиц для кластеризации")
                return {}
            
            face_ids = []
            embeddings = []
            
            for face_id, embedding_bytes, _ in face_data:
                if embedding_bytes:
                    embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                    face_ids.append(face_id)
                    embeddings.append(embedding)
            
            if len(embeddings) < 2:
                logger.info("Недостаточно лиц для кластеризации")
                return {}
            
            # Нормализуем эмбеддинги
            embeddings_norm = [emb / np.linalg.norm(emb) for emb in embeddings]
            embeddings_array = np.array(embeddings_norm)
            
            # Вычисляем матрицу схожести
            similarity_matrix = cosine_similarity(embeddings_array)
            
            # Используем DBSCAN для кластеризации
            # Преобразуем схожесть в расстояние (1 - similarity)
            distance_matrix = 1 - similarity_matrix
            
            # DBSCAN с параметрами для группировки похожих лиц
            clustering = DBSCAN(
                eps=1 - self.similarity_threshold,
                min_samples=1,
                metric='precomputed'
            )
            
            clusters = clustering.fit_predict(distance_matrix)
            
            # Группируем лица по кластерам
            cluster_groups = {}
            for face_id, cluster_id in zip(face_ids, clusters):
                if cluster_id == -1:
                    # Шум - создаем отдельный кластер для каждого лица
                    cluster_id = f"noise_{face_id}"
                
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
                
                # Создаем новую персону для кластера
                person_name = f"Person_{cluster_id}"
                person_id = self.db_manager.create_person(person_name)
                
                if person_id:
                    # Перемещаем все лица кластера к новой персоне
                    for face_id in face_ids:
                        self.db_manager.move_face_to_person(face_id, person_id)
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
            threshold = self.similarity_threshold
            
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