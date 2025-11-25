import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QLineEdit, QDialog, QDialogButtonBox, QMessageBox, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QTimer, QPointF
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QFont, QMouseEvent, QKeyEvent, QAction,
)
from PIL import Image
from tkinter import filedialog  # Для совместимости, но не используется в PyQt
import traceback

class FaceEditDialog(QDialog):
    """Диалог для редактирования имени лица"""
    
    def __init__(self, current_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Изменить имя лица")
        self.setModal(True)
        self.setFixedSize(300, 120)
        self.init_ui(current_name)
        
    def init_ui(self, current_name):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Имя человека:"))
        
        self.name_edit = QLineEdit()
        self.name_edit.setText(current_name or "")
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
    """Представление рамки лица в scene coordinates"""
    
    def __init__(self, face_id, bbox, person_name, confidence):
        # bbox: (x1, y1, x2, y2) в оригинальных пикселях
        self.face_id = face_id
        self.scene_rect = QRectF(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[2] - bbox[1])
        self.person_name = person_name or "Unknown"
        self.confidence = confidence
        self.is_hovered = False
        
    def contains_scene_point(self, scene_pos):
        """Проверка наведения/клика в scene coordinates"""
        return self.scene_rect.contains(scene_pos)
        
    def draw(self, painter, view):
        """Рисует рамку в viewport coordinates"""
        # viewport_rect = view.mapFromScene(self.scene_rect).boundingRect()
        # scene_r = self.scene_rect.toRectF()
        viewport_rect = view.mapFromScene(self.scene_rect).boundingRect()
        # viewport_rect = view.mapFromScene(scene_r).boundingRect()
        
        # Цвет: зеленый для известных, желтый для unknown
        color = QColor(0, 255, 0) if self.person_name != "Unknown" else QColor(255, 255, 0)
        if self.is_hovered:
            color = color.lighter(150)
            
        pen = QPen(color, max(2, 3))
        painter.setPen(pen)
        painter.drawRect(viewport_rect)
        
        # Текст только при достаточном масштабе
        if view.transform().m11() > 0.5:
            self._draw_label(painter, view, viewport_rect)
    
    # def _draw_label(self, painter, view, viewport_rect):
    #     text = self.person_name
    #     if self.confidence < 0.9:
    #         text += f" ({self.confidence:.2f})"
            
    #     font = QFont("Arial", max(8, 12))
    #     font.setBold(True)
    #     painter.setFont(font)
    #     metrics = painter.fontMetrics()
    #     text_rect = metrics.boundingRect(text)
        
    #     # Позиция текста над rect
    #     text_pos = QPointF(viewport_rect.topLeft()) + QPointF(0, -5)
    #     if text_pos.y() < 0:
    #         text_pos = QPointF(viewport_rect.bottomLeft()) + QPointF(0, 5)
            
    #     # Фон
    #     painter.fillRect(
    #         text_pos.x() - 2, text_pos.y() - text_rect.height() - 2,
    #         text_rect.width() + 4, text_rect.height() + 4,
    #         QColor(0, 0, 0, 180)
    #     )
    #     # Текст
    #     painter.setPen(QColor(255, 255, 255))
    #     painter.drawText(text_pos, text_rect.height(), text)
    def _draw_label(self, painter, view, viewport_rect):
        text = self.person_name
        if self.confidence < 0.9:
            text += f" ({self.confidence:.2f})"
            
        font = QFont("Arial", max(8, 12))
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_size = metrics.size(0, text)  # QRectF-like size
        
        # Позиция текста (QPointF)
        text_pos = QPointF(viewport_rect.topLeft()) + QPointF(0, -5)
        if text_pos.y() < 0:
            text_pos = QPointF(viewport_rect.bottomLeft()) + QPointF(0, 5)
        
        # Фон как QRectF (поддерживает float)
        bg_rect = QRectF(
            text_pos.x() - 2, text_pos.y() - text_size.height() - 2,
            text_size.width() + 4, text_size.height() + 4
        )
        painter.fillRect(bg_rect, QColor(0, 0, 0, 180))
        
        # Текст
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, text)

class PhotoViewer(QGraphicsView):
    """Просмотрщик фото с оверлеем рамок лиц"""
    
    face_name_changed = pyqtSignal(int, str)  # face_id, new_name
    closed = pyqtSignal()
    
    def __init__(self, db_manager, config=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.config = config
        self.current_image_path = None
        self.face_rectangles = []
        self._init_ui()
        
    def _init_ui(self):
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.setMouseTracking(True)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        print("Viewer DPR:", self.devicePixelRatioF())  # Test
        
    def load_image(self, image_path):
        """Загружает изображение и лица"""
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "Ошибка", "Файл не существует")
            return False
            
        pixmap = QPixmap(image_path)
        dpr = self.devicePixelRatioF()  # HiDPI factor
        pixmap.setDevicePixelRatio(dpr)
        print(f"Pixmap logical size: {pixmap.width()}x{pixmap.height()} DPR: {dpr}")
        if pixmap.isNull():
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить изображение")
            return False
            
        self.current_image_path = image_path
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        # self.scene.setSceneRect(QRectF(0, 0, pixmap.widthF(), pixmap.heightF()))
        
        self.face_rectangles.clear()
        self.load_face_data(image_path)
        
        self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        return True
        
    def load_face_data(self, image_path):
        """Загружает лица из БД"""
        self.face_rectangles.clear()
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Получаем image_id
                cursor.execute("SELECT id FROM images WHERE file_path = ?", (image_path,))
                img_row = cursor.fetchone()
                if not img_row:
                    print(f"Изображение {image_path} не в БД")
                    return
                image_id = img_row[0]
                
                # Лица (bbox уже absolute!)
                cursor.execute("""
                    SELECT f.id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2, 
                        f.confidence, COALESCE(p.name, 'Unknown')
                    FROM faces f LEFT JOIN persons p ON f.person_id = p.id
                    WHERE f.image_id = ?
                """, (image_id,))
                
                faces_data = cursor.fetchall()
                print(f"Найдено лиц для {image_path}: {len(faces_data)}")
                
                for face_id, x1, y1, x2, y2, conf, name in faces_data:
                    bbox = (x1, y1, x2, y2)  # Уже absolute pixels!
                    print(f"  Лицо {face_id}: bbox({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}) size({x2-x1:.0f}x{y2-y1:.0f})")
                    
                    self.face_rectangles.append(FaceRectangle(face_id, bbox, name, conf))
                    
        except Exception as e:
            print(f"Ошибка load_face_data {image_path}: {e}")
            traceback.print_exc()
    
    def drawForeground(self, painter, rect):
        """Рисует оверлей рамок"""
        if not self.face_rectangles:
            return
        painter.save()
        for rect_item in self.face_rectangles:
            rect_item.draw(painter, self)
        painter.restore()
        
    def mouseMoveEvent(self, event):
        """Наведение на рамки"""
        scene_pos = self.mapToScene(event.pos())
        hovered = False
        for face_rect in self.face_rectangles:
            was_hovered = face_rect.is_hovered
            face_rect.is_hovered = face_rect.contains_scene_point(scene_pos)
            if face_rect.is_hovered:
                hovered = True
            if face_rect.is_hovered != was_hovered:
                self.viewport().update()
                # self.viewport().update(self.mapToScene(event.pos()).boundingRect().adjusted(-50, -50, 50, 50))  # Локальный redraw
                
        # self.setCursor(Qt.PointingHandCursor if hovered else Qt.ArrowCursor)
        self.setCursor(Qt.CursorShape.PointingHandCursor if hovered else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)
        
    def mousePressEvent(self, event):
        # if event.button() == Qt.LeftButton:
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            for face_rect in self.face_rectangles:
                if face_rect.contains_scene_point(scene_pos):
                    self.edit_face_name(face_rect)
                    break
        super().mousePressEvent(event)
        
    def wheelEvent(self, event):
        """Zoom колесиком"""
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.closed.emit()
        elif event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.scale(1.2, 1.2)
        elif event.key() == Qt.Key.Key_Minus:
            self.scale(0.8, 0.8)
        elif event.key() == Qt.Key.Key_0:
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        super().keyPressEvent(event)
        
    def edit_face_name(self, face_rect):
        dialog = FaceEditDialog(face_rect.person_name, self)
        # if dialog.exec() == QDialog.Accepted:
        if dialog.exec() == QDialog.DialogCode.Accepted:    
            new_name = dialog.get_name()
            if new_name and new_name != face_rect.person_name:
                if self._update_face_name(face_rect.face_id, new_name):
                    face_rect.person_name = new_name
                    self.viewport().update()
                    self.face_name_changed.emit(face_rect.face_id, new_name)
                    
    def _update_face_name(self, face_id, new_name):
        try:
            person_id = self.db_manager.get_person_by_name(new_name)
            if not person_id:
                person_id = self.db_manager.create_person(new_name)
            return person_id and self.db_manager.move_face_to_person(face_id, person_id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка обновления: {e}")
            return False

class PhotoViewerWindow(QWidget):
    """Главное окно просмотра"""
    
    closed = pyqtSignal()
    
    def __init__(self, db_manager, config=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.config = config
        self.is_fullscreen = False
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.viewer = PhotoViewer(self.db_manager, self.config, self)
        self.viewer.closed.connect(self.close)
        layout.addWidget(self.viewer)
        
        # Панель управления
        self._create_control_panel()
        
        self.setWindowTitle("Photo Viewer")
        self.resize(1200, 800)
        
    def _create_control_panel(self):
        self.control_panel = QWidget()
        self.control_panel.setFixedHeight(45)
        layout = QHBoxLayout(self.control_panel)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.control_panel.setStyleSheet("""
            QWidget { background: rgba(0,0,0,0.7); border-radius: 8px; color: white; }
            QPushButton { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); 
                          border-radius: 4px; padding: 5px; min-width: 30px; color: white; font-weight: bold; }
            QPushButton:hover { background: rgba(255,255,255,0.4); }
        """)
        
        btns = [
            ("+", self.viewer.scale, (1.2, 1.2), "Zoom In"),
            ("-", self.viewer.scale, (0.8, 0.8), "Zoom Out"),
            # ("Fit", lambda: self.viewer.fitInView(self.viewer.scene.itemsBoundingRect(), Qt.KeepAspectRatio), None, "Fit to Window"),
            ("Fit", lambda: self.viewer.fitInView(self.viewer.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio), None, "Fit to Window"),

            ("FS", self.toggle_fullscreen, None, "Fullscreen (F)"),
            ("✕", self.close, None, "Close (Esc)"),
        ]
        
        for text, func, args, tip in btns:
            btn = QPushButton(text)
            btn.setToolTip(tip)
            if args:
                btn.clicked.connect(lambda _, f=func, a=args: f(*a))
            else:
                btn.clicked.connect(func)
            layout.addWidget(btn)
        
        layout.addStretch()
        self.control_panel.setParent(self)
        
    def show_image(self, image_path):
        if self.viewer.load_image(image_path):
            QTimer.singleShot(100, self._auto_fit)
            self.show()
            self.activateWindow()
            self.raise_()
            return True
        return False
        
    def _auto_fit(self):
        # self.viewer.fitInView(self.viewer.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        self.viewer.fitInView(self.viewer.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self._auto_fit)
        # Переместить панель в угол
        self.control_panel.move(self.width() - self.control_panel.width() - 20, 20)
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape:
            if self.is_fullscreen:
                self.toggle_fullscreen()
            else:
                self.close()
        super().keyPressEvent(event)
                
    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.showFullScreen()
            self.setCursor(Qt.CursorShape.BlankCursor)
        else:
            self.showNormal()
            self.setCursor(Qt.CursorShape.ArrowCursor)
            
    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)