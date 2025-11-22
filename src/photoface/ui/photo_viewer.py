import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGraphicsView, QGraphicsScene, 
                             QGraphicsPixmapItem, QLineEdit, QDialog, 
                             QDialogButtonBox, QMessageBox, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRectF, QTimer
from PyQt6.QtGui import (QPixmap, QImage, QPainter, QPen, QColor, QFont,
                         QMouseEvent, QKeyEvent, QAction)
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np

class FaceEditDialog(QDialog):
    """Диалог для редактирования имени лица"""
    
    def __init__(self, current_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Изменить имя")
        self.setModal(True)
        self.setFixedSize(300, 120)
        self.init_ui(current_name)
        
    def init_ui(self, current_name):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Имя человека:"))
        
        self.name_edit = QLineEdit()
        self.name_edit.setText(current_name)
        self.name_edit.selectAll()
        self.name_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.name_edit)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_name(self):
        return self.name_edit.text().strip()

class FaceRectangle:
    """Класс для представления рамки лица"""
    
    def __init__(self, face_id, bbox, person_name, confidence, image_size):
        self.face_id = face_id
        self.bbox = bbox  # (x1, y1, x2, y2)
        self.person_name = person_name
        self.confidence = confidence
        self.image_size = image_size  # (width, height)
        self.is_hovered = False
        self.edit_mode = False

    def contains_point(self, point, view_scale=1.0, image_scale=1.0):
        """Проверяет, содержит ли рамка точку с учетом масштабов"""
        x1, y1, x2, y2 = self.get_scaled_bbox(view_scale, image_scale)
        return x1 <= point.x() <= x2 and y1 <= point.y() <= y2
        
    def get_scaled_bbox(self, view_scale=1.0, image_scale=1.0):
        """Возвращает координаты рамки с учетом масштаба просмотра и исходного изображения"""
        x1, y1, x2, y2 = self.bbox
        
        # print(f"Оригинальные координаты: ({x1}, {y1}, {x2}, {y2})")  # Отладка
        # print(f"Масштабы: view={view_scale}, image={image_scale}")  # Отладка
        
        # Применяем масштаб исходного изображения
        x1_scaled = x1 * image_scale
        y1_scaled = y1 * image_scale
        x2_scaled = x2 * image_scale
        y2_scaled = y2 * image_scale
        
        # Применяем масштаб просмотра
        x1_scaled *= view_scale
        y1_scaled *= view_scale
        x2_scaled *= view_scale
        y2_scaled *= view_scale
        
        # print(f"Масштабированные координаты: ({x1_scaled}, {y1_scaled}, {x2_scaled}, {y2_scaled})")  # Отладка
        
        return x1_scaled, y1_scaled, x2_scaled, y2_scaled
        
    def draw(self, painter, view_scale=1.0, image_scale=1.0):
        """Рисует рамку на QPainter с учетом масштабов"""
        x1, y1, x2, y2 = self.get_scaled_bbox(view_scale, image_scale)
        
        # Цвет рамки в зависимости от подтверждения
        if self.person_name and self.person_name != 'not recognized':
            color = QColor(0, 255, 0)  # Зеленый для распознанных
        else:
            color = QColor(255, 255, 0)  # Желтый для нераспознанных
            
        if self.is_hovered:
            color = color.lighter(150)  # Осветляем при наведении
            
        pen = QPen(color)
        pen.setWidth(max(2, int(3 * view_scale)))  # Масштабируем толщину линии
        painter.setPen(pen)
        
        # Рисуем прямоугольник
        painter.drawRect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        
        # Рисуем текст с именем (только при достаточном масштабе)
        if view_scale > 0.3:  # Не показываем текст при сильном уменьшении
            font = QFont()
            font.setPointSize(max(8, int(12 * view_scale)))
            font.setBold(True)
            painter.setFont(font)
            
            text = self.person_name if self.person_name else 'Unknown'
            if self.confidence < 0.9:  # Показываем confidence если низкий
                text += f" ({self.confidence:.2f})"
                
            text_rect = painter.fontMetrics().boundingRect(text)
            text_width = text_rect.width()
            text_height = text_rect.height()
            
            # Позиционируем текст над рамкой
            text_x = x1
            text_y = y1 - text_height - 5
            
            # Если текст выходит за границы, перемещаем его
            if text_y < 0:
                text_y = y2 + 5
                
            # Рисуем фон для текста
            painter.fillRect(
                int(text_x) - 2, int(text_y) - 2,
                text_width + 4, text_height + 4,
                QColor(0, 0, 0, 180)
            )
            
            # Рисуем текст
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(int(text_x), int(text_y) + text_height - 3, text)

class PhotoViewer(QGraphicsView):
    """Виджет для просмотра фотографий с рамками лиц"""
    
    face_name_changed = pyqtSignal(int, str)  # face_id, new_name
    closed = pyqtSignal()
    
    def __init__(self, db_manager, config=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.config = config
        self.current_image_path = None
        self.face_rectangles = []
        self.scale_factor = 1.0
        current_image_scale = 1.0
        self.init_ui()
        
    def init_ui(self):
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # Включаем прокрутку
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Сцена для отображения изображения
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # Элемент изображения
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        # Таймер для скрытия курсора
        self.cursor_timer = QTimer()
        self.cursor_timer.timeout.connect(self.hide_cursor)
        self.cursor_timer.setSingleShot(True)
        
        # Устанавливаем обработчики событий
        self.setMouseTracking(True)
        
    def load_image(self, image_path):
        """Загружает изображение и информацию о лицах"""
        print(f"PhotoViewer: загрузка изображения {image_path}")
        self.current_image_path = image_path
        
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "Ошибка", "Файл не существует")
            return False
            
        try:
            # Загружаем изображение
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                print(f"Не удалось загрузить изображение: {image_path}")
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить изображение")
                return False
                
            self.pixmap_item.setPixmap(pixmap)
            self.scene.setSceneRect(QRectF(pixmap.rect()))
            
            # Получаем информацию о лицах из базы данных
            self.load_face_data(image_path)
            
            # Автоматически подгоняем размер под виджет
            self.fit_to_view()
            
            # Запускаем таймер скрытия курсора
            self.cursor_timer.start(2000)
            
            print("Изображение успешно загружено в PhotoViewer")
            return True
            
        except Exception as e:
            print(f"Ошибка загрузки изображения в PhotoViewer: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки изображения: {e}")
            return False
            
    def load_face_data(self, image_path):
        """Загружает данные о лицах для изображения"""
        self.face_rectangles = []
        
        try:
            # Получаем информацию об изображении из БД
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT i.id FROM images i WHERE i.file_path = ?
                ''', (image_path,))
                result = cursor.fetchone()
                
                if not result:
                    return
                    
                image_id = result[0]
                
                # Получаем все лица для этого изображения
                cursor.execute('''
                    SELECT f.id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2, 
                           f.confidence, p.name
                    FROM faces f
                    JOIN persons p ON f.person_id = p.id
                    WHERE f.image_id = ?
                ''', (image_id,))
                
                faces = cursor.fetchall()
                
                # Получаем размер оригинального изображения
                from PIL import Image
                with Image.open(image_path) as img:
                    image_size = img.size
                
                # Создаем объекты рамок
                for face_id, x1, y1, x2, y2, confidence, person_name in faces:
                    face_rect = FaceRectangle(
                        face_id=face_id,
                        bbox=(x1, y1, x2, y2),
                        person_name=person_name,
                        confidence=confidence,
                        image_size=image_size
                    )
                    self.face_rectangles.append(face_rect)
                    
        except Exception as e:
            print(f"Ошибка загрузки данных о лицах: {e}")
            
    def drawForeground(self, painter, rect):
        """Переопределяем метод для рисования рамок поверх изображения"""
        if not self.face_rectangles:
            return
            
        # Сохраняем состояние painter
        painter.save()
        
        # Получаем текущий масштаб просмотра
        transform = self.transform()
        view_scale = transform.m11()  # Горизонтальный масштаб
        
        # Получаем масштаб изображения относительно оригинала
        image_scale = getattr(self, 'current_image_scale', 1.0)
        
        # Отладочная информация (можно убрать после исправления)
        if not hasattr(self, '_debug_printed'):
            print(f"Debug - View scale: {view_scale}, Image scale: {image_scale}")
            print(f"Debug - Face rectangles count: {len(self.face_rectangles)}")
            if self.face_rectangles:
                print(f"Debug - Original bbox: {self.face_rectangles[0].bbox}")
                scaled_bbox = self.face_rectangles[0].get_scaled_bbox(view_scale, image_scale)
                print(f"Debug - Scaled bbox: {scaled_bbox}")
            self._debug_printed = True
        
        # Рисуем все рамки
        for face_rect in self.face_rectangles:
            face_rect.draw(painter, view_scale, image_scale)
            
        painter.restore()
        
    def mouseMoveEvent(self, event):
        """Обрабатывает движение мыши"""
        # Сбрасываем таймер скрытия курсора
        self.cursor_timer.start(2000)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # Получаем текущие масштабы
        transform = self.transform()
        view_scale = transform.m11()
        image_scale = getattr(self, 'current_image_scale', 1.0)
        
        # Проверяем наведение на рамки
        scene_pos = self.mapToScene(event.pos())
        any_hovered = False
        
        for face_rect in self.face_rectangles:
            was_hovered = face_rect.is_hovered
            face_rect.is_hovered = face_rect.contains_point(scene_pos, view_scale, image_scale)
            
            if face_rect.is_hovered:
                any_hovered = True
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                
            # Обновляем сцену если состояние изменилось
            if was_hovered != face_rect.is_hovered:
                self.scene.update()
                
        super().mouseMoveEvent(event)
        
    def mousePressEvent(self, event):
        """Обрабатывает клик мыши"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Получаем текущие масштабы
            transform = self.transform()
            view_scale = transform.m11()
            image_scale = getattr(self, 'current_image_scale', 1.0)
            
            scene_pos = self.mapToScene(event.pos())
            
            # Проверяем клик по рамке
            for face_rect in self.face_rectangles:
                if face_rect.contains_point(scene_pos, view_scale, image_scale):
                    self.edit_face_name(face_rect)
                    break
                    
        super().mousePressEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        """Обрабатывает двойной клик - закрытие просмотра"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.close_viewer()
        else:
            super().mouseDoubleClickEvent(event)
            
    def keyPressEvent(self, event):
        """Обрабатывает нажатия клавиш"""
        if event.key() == Qt.Key.Key_Escape:
            self.close_viewer()
        elif event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
            self.zoom_in()
        elif event.key() == Qt.Key.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key.Key_0:
            self.fit_to_view()
        elif event.key() == Qt.Key.Key_F:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)
            
    def edit_face_name(self, face_rect):
        """Редактирует имя лица"""
        dialog = FaceEditDialog(face_rect.person_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.get_name()
            if new_name and new_name != face_rect.person_name:
                # Обновляем в базе данных
                if self.update_face_name(face_rect.face_id, new_name):
                    face_rect.person_name = new_name
                    self.scene.update()
                    self.face_name_changed.emit(face_rect.face_id, new_name)
                    
    def update_face_name(self, face_id, new_name):
        """Обновляет имя лица в базе данных"""
        try:
            # Находим или создаем персону с новым именем
            person_id = self.db_manager.get_person_by_name(new_name)
            if not person_id:
                person_id = self.db_manager.create_person(new_name)
                
            if person_id:
                # Перемещаем лицо к новой персоне
                return self.db_manager.move_face_to_person(face_id, person_id)
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка обновления имени: {e}")
            
        return False
        
    def zoom_in(self):
        """Увеличивает масштаб"""
        self.scale(1.2, 1.2)
        
    def zoom_out(self):
        """Уменьшает масштаб"""
        self.scale(0.8, 0.8)
        
    def fit_to_view(self):
        """Подгоняет изображение под размер виджета"""
        if not self.scene.itemsBoundingRect().isEmpty():
            # Подгоняем с сохранением пропорций
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            # Обновляем масштаб
            self.update_image_scale()
            # Обновляем сцену
            self.scene.update()

    def toggle_fullscreen(self):
        """Переключает полноэкранный режим"""
        if self.parent() and hasattr(self.parent(), 'toggle_fullscreen'):
            self.parent().toggle_fullscreen()
            
    def hide_cursor(self):
        """Скрывает курсор"""
        self.setCursor(Qt.CursorShape.BlankCursor)
        
    def close_viewer(self):
        """Закрывает просмотрщик"""
        self.closed.emit()

    def update_image_scale(self):
        """Обновляет масштаб изображения при изменении размера"""
        if not self.scene.itemsBoundingRect().isEmpty() and self.face_rectangles:
            # Получаем размер оригинального изображения
            orig_width, orig_height = self.face_rectangles[0].image_size
            
            # Получаем размер viewport (видимой области)
            viewport_size = self.viewport().size()
            viewport_width = viewport_size.width()
            viewport_height = viewport_size.height()
            
            # Получаем размер сцены (оригинального изображения)
            scene_rect = self.scene.itemsBoundingRect()
            scene_width = scene_rect.width()
            scene_height = scene_rect.height()
            
            # Вычисляем фактический масштаб отображения
            if scene_width > 0 and scene_height > 0 and viewport_width > 0 and viewport_height > 0:
                # Масштаб вычисляем на основе того, как изображение фактически отображается
                # в viewport с учетом режима KeepAspectRatio
                scale_x = viewport_width / scene_width
                scale_y = viewport_height / scene_height
                
                # В режиме KeepAspectRatio используется минимальный масштаб
                self.current_image_scale = min(scale_x, scale_y)
                
                print(f"Updated image scale: {self.current_image_scale:.3f}")  # Для отладки
                print(f"Original: {orig_width}x{orig_height}, Scene: {scene_width:.1f}x{scene_height:.1f}, Viewport: {viewport_width}x{viewport_height}")
            else:
                self.current_image_scale = 1.0

    def resizeEvent(self, event):
        """Обрабатывает изменение размера виджета"""
        super().resizeEvent(event)
        # Обновляем масштаб при изменении размера
        # self.update_image_scale()
        # Обновляем масштаб при изменении размера с небольшой задержкой
        QTimer.singleShot(50, self.update_image_scale)
        self.scene.update()

class PhotoViewerWindow(QWidget):
    """Оконный просмотрщик фотографий"""
    
    closed = pyqtSignal()
    
    def __init__(self, db_manager, config=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.config = config
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Создаем просмотрщик
        self.photo_viewer = PhotoViewer(self.db_manager, self.config, self)
        self.photo_viewer.closed.connect(self.close)
        self.photo_viewer.face_name_changed.connect(self.on_face_name_changed)
        
        layout.addWidget(self.photo_viewer)
        
        # Панель управления
        self.control_panel = QWidget()
        self.control_panel.setFixedHeight(40)
        control_layout = QHBoxLayout(self.control_panel)
        control_layout.setContentsMargins(5, 2, 5, 2)
        
        # self.control_panel.setStyleSheet("""
        #     QWidget {
        #         background-color: rgba(0, 0, 0, 150);
        #         border-radius: 5px;
        #     }
        # """)
        self.control_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 8px;
                padding: 5px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 200);
                border: 1px solid rgba(0, 0, 0, 100);
                border-radius: 4px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 255);
            }
        """)
        
        # Кнопки управления
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(30, 30)
        self.zoom_in_btn.clicked.connect(self.photo_viewer.zoom_in)
        self.zoom_in_btn.setToolTip("Увеличить")
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedSize(30, 30)
        self.zoom_out_btn.clicked.connect(self.photo_viewer.zoom_out)
        self.zoom_out_btn.setToolTip("Уменьшить")
        
        self.fit_btn = QPushButton("Fit")
        self.fit_btn.setFixedSize(40, 30)
        self.fit_btn.clicked.connect(self.photo_viewer.fit_to_view)
        self.fit_btn.setToolTip("Подогнать под окно")
        
        self.close_btn = QPushButton("Закрыть (Esc)")
        self.close_btn.setFixedSize(100, 30)
        self.close_btn.clicked.connect(self.close)
        
        control_layout.addWidget(self.zoom_in_btn)
        control_layout.addWidget(self.zoom_out_btn)
        control_layout.addWidget(self.fit_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.close_btn)
        
        # Размещаем панель управления поверх просмотрщика
        self.control_panel.setParent(self)
        self.control_panel.move(20, 20)
        
        # Настройки окна
        self.setWindowTitle("Просмотр фотографии")
        self.setGeometry(100, 100, 1000, 700)
        self.setMinimumSize(400, 300)
        
    def show_image(self, image_path):
        """Показывает изображение в окне"""
        print(f"PhotoViewerWindow: показ изображения {image_path}")
        
        if self.photo_viewer.load_image(image_path):
            # Сразу подгоняем изображение под окно
            # QTimer.singleShot(50, self.photo_viewer.fit_to_view)  # Небольшая задержка для гарантии
            QTimer.singleShot(100, lambda: [
                self.photo_viewer.fit_to_view(),
                self.photo_viewer.update_image_scale()  # Добавляем явный вызов
            ])
            
            # Показываем окно
            self.show()
            self.activateWindow()
            self.raise_()
            
            # Устанавливаем фокус
            self.setFocus()
            
            print("Окно просмотрщика успешно показано")
            return True
        
        print("Не удалось загрузить изображение")
        return False
        
    def resizeEvent(self, event):
        """Обрабатывает изменение размера окна"""
        super().resizeEvent(event)
        # При изменении размера окна автоматически подгоняем изображение
        QTimer.singleShot(50, self.photo_viewer.fit_to_view)
    
        # Перемещаем панель управления в правый верхний угол
        self.control_panel.move(self.width() - self.control_panel.width() - 20, 20)
        
    def close(self):
        """Закрывает просмотрщик"""
        print("Закрытие PhotoViewerWindow")
        self.closed.emit()
        super().close()
        
    def on_face_name_changed(self, face_id, new_name):
        """Обрабатывает изменение имени лица"""
        pass
        
    def keyPressEvent(self, event):
        """Обрабатывает нажатия клавиш"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_F:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_0:
            self.photo_viewer.fit_to_view()
        else:
            super().keyPressEvent(event)
            
    def toggle_fullscreen(self):
        """Переключает полноэкранный режим (опционально)"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

# class FullScreenPhotoViewer(QWidget):
#     """Полноэкранный просмотрщик фотографий"""
    
#     closed = pyqtSignal()
    
#     def __init__(self, db_manager, config=None, parent=None):
#         super().__init__(parent)
#         self.db_manager = db_manager
#         self.config = config
#         self.is_fullscreen = False
#         self.init_ui()
        
#     def init_ui(self):
#         layout = QVBoxLayout(self)
#         layout.setContentsMargins(0, 0, 0, 0)
        
#         # Создаем просмотрщик
#         self.photo_viewer = PhotoViewer(self.db_manager, self.config, self)
#         self.photo_viewer.closed.connect(self.close)
#         self.photo_viewer.face_name_changed.connect(self.on_face_name_changed)
        
#         layout.addWidget(self.photo_viewer)
        
#         # Панель управления (изначально скрыта)
#         self.control_panel = QWidget()
#         control_layout = QHBoxLayout(self.control_panel)
#         control_layout.setContentsMargins(10, 5, 10, 5)
        
#         self.control_panel.setStyleSheet("""
#             QWidget {
#                 background-color: rgba(0, 0, 0, 150);
#                 border-radius: 5px;
#             }
#         """)
        
#         # Кнопки управления
#         self.zoom_in_btn = QPushButton("+")
#         self.zoom_in_btn.setFixedSize(30, 30)
#         self.zoom_in_btn.clicked.connect(self.photo_viewer.zoom_in)
        
#         self.zoom_out_btn = QPushButton("-")
#         self.zoom_out_btn.setFixedSize(30, 30)
#         self.zoom_out_btn.clicked.connect(self.photo_viewer.zoom_out)
        
#         self.fit_btn = QPushButton("Fit")
#         self.fit_btn.setFixedSize(40, 30)
#         self.fit_btn.clicked.connect(self.photo_viewer.fit_to_view)
        
#         self.close_btn = QPushButton("Закрыть (Esc)")
#         self.close_btn.setFixedSize(100, 30)
#         self.close_btn.clicked.connect(self.close)
        
#         control_layout.addWidget(self.zoom_in_btn)
#         control_layout.addWidget(self.zoom_out_btn)
#         control_layout.addWidget(self.fit_btn)
#         control_layout.addStretch()
#         control_layout.addWidget(self.close_btn)
        
#         # Размещаем панель управления поверх просмотрщика
#         self.control_panel.setParent(self)
#         self.control_panel.move(20, 20)
#         self.control_panel.hide()
        
#         # Таймер для скрытия панели управления
#         self.panel_timer = QTimer()
#         self.panel_timer.timeout.connect(self.hide_control_panel)
#         self.panel_timer.setSingleShot(True)
        
#     def show_image(self, image_path):
#         """Показывает изображение в полноэкранном режиме"""
#         print(f"FullScreenPhotoViewer: показ изображения {image_path}")  # Отладочная информация
        
#         if self.photo_viewer.load_image(image_path):
#             self.show_fullscreen()

#             # Принудительно обновляем отображение
#             self.update()
#             self.repaint()

#             return True
#         print("Не удалось загрузить изображение в FullScreenPhotoViewer")
#         return False
#     # def show_image(self, image_path):
#     #     """Показывает изображение в полноэкранном режиме"""
#     #     print(f"Попытка загрузить изображение: {image_path}")  # Отладочная информация
#     #     self.current_image_path = image_path
        
#     #     if not os.path.exists(image_path):
#     #         QMessageBox.warning(self, "Ошибка", "Файл не существует")
#     #         return False
            
#     #     try:
#     #         # Загружаем изображение
#     #         pixmap = QPixmap(image_path)
#     #         if pixmap.isNull():
#     #             QMessageBox.warning(self, "Ошибка", "Не удалось загрузить изображение")
#     #             return False
                
#     #         self.pixmap_item.setPixmap(pixmap)
#     #         self.scene.setSceneRect(QRectF(pixmap.rect()))
            
#     #         # Получаем информацию о лицах из базы данных
#     #         self.load_face_data(image_path)
            
#     #         # Подгоняем размер под виджет
#     #         self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            
#     #         # Запускаем таймер скрытия курсора
#     #         self.cursor_timer.start(2000)
            
#     #         print("Изображение успешно загружено")  # Отладочная информация
#     #         return True
            
#     #     except Exception as e:
#     #         print(f"Ошибка загрузки изображения: {e}")  # Отладочная информация
#     #         QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки изображения: {e}")
#     #         return False
        
#     # def show_fullscreen(self):
#     #     """Показывает виджет в полноэкранном режиме"""
#     #     self.is_fullscreen = True
#     #     self.showMaximized()
#     #     self.raise_()
#     #     self.activateWindow()
        
#     #     # Показываем панель управления на несколько секунд
#     #     self.show_control_panel()
#     def show_fullscreen(self):
#         """Показывает виджет в полноэкранном режиме"""
#         print("Активация полноэкранного режима")  # Отладочная информация
        
#         # Убедимся, что окно правильно инициализировано
#         print(f"Window flags: {self.windowFlags()}")
#         print(f"Window state: {self.windowState()}")
#         print(f"Window visible: {self.isVisible()}")
        
#         self.is_fullscreen = True
        
#         # Показываем окно перед переходом в полноэкранный режим
#         self.show()
#         self.activateWindow()
#         self.raise_()
        
#         # Переходим в полноэкранный режим
#         self.showFullScreen()
        
#         # Убедимся, что окно активно
#         self.setFocus(Qt.FocusReason.PopupFocusReason)
        
#         print(f"После showFullScreen - visible: {self.isVisible()}, active: {self.isActiveWindow()}")
        
#         # Показываем панель управления на несколько секунд
#         self.show_control_panel()
        
#     def show_control_panel(self):
#         """Показывает панель управления"""
#         self.control_panel.show()
#         self.control_panel.raise_()
#         self.panel_timer.start(3000)  # Скрыть через 3 секунды
        
#     def hide_control_panel(self):
#         """Скрывает панель управления"""
#         if not self.control_panel.underMouse():
#             self.control_panel.hide()
            
#     def mousePressEvent(self, event):
#         """Обрабатывает клик мыши"""
#         if event.button() == Qt.MouseButton.LeftButton:
#             # Показываем панель управления при клике
#             self.show_control_panel()
#         super().mousePressEvent(event)
        
#     def mouseMoveEvent(self, event):
#         """Обрабатывает движение мыши"""
#         # Показываем панель управления при движении мыши
#         if not self.control_panel.isVisible():
#             self.show_control_panel()
#         self.panel_timer.start(3000)  # Перезапускаем таймер
#         super().mouseMoveEvent(event)
        
#     def keyPressEvent(self, event):
#         """Обрабатывает нажатия клавиш"""
#         if event.key() == Qt.Key.Key_Escape:
#             self.close()
#         elif event.key() == Qt.Key.Key_F:
#             self.toggle_fullscreen()
#         else:
#             super().keyPressEvent(event)
            
#     def toggle_fullscreen(self):
#         """Переключает полноэкранный режим"""
#         if self.isFullScreen():
#             self.showNormal()
#             self.is_fullscreen = False
#         else:
#             self.showFullScreen()
#             self.is_fullscreen = True
            
#     def close(self):
#         """Закрывает просмотрщик"""
#         print("Закрытие FullScreenPhotoViewer")  # Отладочная информация
#         self.closed.emit()
#         super().close()
        
#     def on_face_name_changed(self, face_id, new_name):
#         """Обрабатывает изменение имени лица"""
#         # Можно добавить дополнительную логику при изменении имени
#         pass
#     def showEvent(self, event):
#         """Обрабатывает событие показа окна"""
#         super().showEvent(event)
#         print("showEvent - FullScreenPhotoViewer показан")  # Отладочная информация
#         self.setFocus()  # Устанавливаем фокус на окно