import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListView, QGridLayout, QPushButton, QMessageBox,
                             QMenu, QProgressDialog, QLabel, QLineEdit, 
                             QDialog, QDialogButtonBox, QScrollArea, 
                             QCheckBox, QFrame, QSizePolicy, QToolButton)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QPixmap, QIcon, QFont, QAction
from src.photoface.core.database import DatabaseManager
from src.photoface.core.face_clusterer import FaceClusterer
from src.photoface.utils.helpers import generate_thumbnail, pil_to_pixmap

class FaceThumbnailWidget(QFrame):
    """Виджет для отображения миниатюры лица с кнопками действий"""
    
    face_confirmed = pyqtSignal(int)  # face_id
    face_rejected = pyqtSignal(int)   # face_id
    face_double_clicked = pyqtSignal(str)  # image_path
    
    def __init__(self, face_id, image_path, bbox, confidence, parent=None):
        super().__init__(parent)
        self.face_id = face_id
        self.image_path = image_path
        self.bbox = bbox
        self.confidence = confidence
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Миниатюра лица
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(120, 120)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet("border: 1px solid #ccc; background-color: white;")
        
        # Загружаем и обрезаем миниатюру лица
        self.load_face_thumbnail()
        
        # Кнопки действий
        buttons_layout = QHBoxLayout()
        
        self.confirm_btn = QToolButton()
        self.confirm_btn.setIcon(QIcon.fromTheme("dialog-ok-apply"))
        self.confirm_btn.setToolTip("Подтвердить лицо")
        self.confirm_btn.setFixedSize(20, 20)
        self.confirm_btn.clicked.connect(lambda: self.face_confirmed.emit(self.face_id))
        
        self.reject_btn = QToolButton()
        self.reject_btn.setIcon(QIcon.fromTheme("dialog-cancel"))
        self.reject_btn.setToolTip("Отклонить лицо")
        self.reject_btn.setFixedSize(20, 20)
        self.reject_btn.clicked.connect(lambda: self.face_rejected.emit(self.face_id))
        
        buttons_layout.addWidget(self.confirm_btn)
        buttons_layout.addWidget(self.reject_btn)
        buttons_layout.addStretch()
        
        # Информация о confidence
        confidence_label = QLabel(f"{self.confidence:.2f}")
        confidence_label.setStyleSheet("font-size: 10px; color: #666;")
        buttons_layout.addWidget(confidence_label)
        
        layout.addWidget(self.thumbnail_label)
        layout.addLayout(buttons_layout)
        
        # Обработка двойного клика
        self.thumbnail_label.mouseDoubleClickEvent = self.thumbnail_double_clicked
        
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 3px; }")
        
    def load_face_thumbnail(self):
        """Загружает и обрезает миниатюру лица"""
        try:
            # Генерируем миниатюру всего изображения
            thumbnail = generate_thumbnail(self.image_path, size=(200, 200))
            if thumbnail:
                # Обрезаем область лица
                x1, y1, x2, y2 = self.bbox
                # Масштабируем координаты к размеру миниатюры
                img_width, img_height = thumbnail.size
                orig_width, orig_height = self.get_original_image_size()
                
                if orig_width and orig_height:
                    scale_x = img_width / orig_width
                    scale_y = img_height / orig_height
                    
                    x1_scaled = int(x1 * scale_x)
                    y1_scaled = int(y1 * scale_y)
                    x2_scaled = int(x2 * scale_x)
                    y2_scaled = int(y2 * scale_y)
                    
                    # Обрезаем область лица
                    face_thumb = thumbnail.crop((x1_scaled, y1_scaled, x2_scaled, y2_scaled))
                    face_thumb = face_thumb.resize((120, 120))
                    
                    pixmap = pil_to_pixmap(face_thumb)
                    self.thumbnail_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Ошибка загрузки миниатюры лица: {e}")
            
    def get_original_image_size(self):
        """Возвращает размер оригинального изображения"""
        from PIL import Image
        try:
            with Image.open(self.image_path) as img:
                return img.size
        except:
            return None
            
    def thumbnail_double_clicked(self, event):
        """Обрабатывает двойной клик на миниатюре"""
        self.face_double_clicked.emit(self.image_path)

class PersonNameDialog(QDialog):
    """Диалог для ввода имени персоны"""
    
    def __init__(self, current_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Изменить имя персоны")
        self.setModal(True)
        self.init_ui(current_name)
        
    def init_ui(self, current_name):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Введите имя персоны:"))
        
        self.name_edit = QLineEdit()
        self.name_edit.setText(current_name)
        self.name_edit.selectAll()
        layout.addWidget(self.name_edit)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_name(self):
        return self.name_edit.text().strip()

class FacesTab(QWidget):
    """Вкладка для работы с лицами и группировки"""
    
    image_double_clicked = pyqtSignal(str)
    needs_refresh = pyqtSignal()
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self.face_clusterer = FaceClusterer(db_manager)
        self.current_person_id = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        self.cluster_btn = QPushButton("Группировать лица")
        self.cluster_btn.clicked.connect(self.cluster_faces)
        
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        self.stats_label = QLabel("Загрузка...")
        
        toolbar_layout.addWidget(self.cluster_btn)
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addWidget(self.stats_label)
        toolbar_layout.addStretch()
        
        layout.addLayout(toolbar_layout)
        
        # Основной разделитель
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Левая панель - список персон
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        
        left_layout.addWidget(QLabel("Персоны:"))
        
        self.persons_list = QListView()
        self.persons_model = QStandardItemModel()
        self.persons_list.setModel(self.persons_model)
        self.persons_list.clicked.connect(self.on_person_selected)
        self.persons_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.persons_list.customContextMenuRequested.connect(self.show_person_context_menu)
        
        left_layout.addWidget(self.persons_list)
        
        splitter.addWidget(self.left_panel)
        
        # Правая панель - лица выбранной персоны
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        
        right_layout.addWidget(QLabel("Лица:"))
        
        # Scroll area для миниатюр лиц
        self.scroll_area = QScrollArea()
        self.faces_widget = QWidget()
        self.faces_layout = QGridLayout(self.faces_widget)
        self.faces_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.faces_widget)
        self.scroll_area.setWidgetResizable(True)
        
        right_layout.addWidget(self.scroll_area)
        
        splitter.addWidget(self.right_panel)
        
        # Установка пропорций
        splitter.setSizes([300, 900])
        layout.addWidget(splitter)
        
        # Загружаем данные
        self.refresh_data()
        
    def refresh_data(self):
        """Обновляет данные в интерфейсе"""
        self.load_persons()
        self.update_stats()
        
    def load_persons(self):
        """Загружает список персон"""
        self.persons_model.clear()
        persons = self.db_manager.get_person_stats()
        
        for person_id, name, is_confirmed, face_count in persons:
            display_name = f"{name} ({face_count})"
            if not is_confirmed:
                display_name = f"* {display_name}"
                
            item = QStandardItem(display_name)
            item.setData(person_id, Qt.ItemDataRole.UserRole)
            item.setData(name, Qt.ItemDataRole.UserRole + 1)
            item.setData(is_confirmed, Qt.ItemDataRole.UserRole + 2)
            
            # Выделяем неподтвержденные персоны
            if not is_confirmed:
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
                item.setForeground(Qt.GlobalColor.gray)
                
            self.persons_model.appendRow(item)
            
    def update_stats(self):
        """Обновляет статистику"""
        total_faces = self.db_manager.get_unrecognized_faces_count()
        persons_stats = self.db_manager.get_person_stats()
        confirmed_persons = sum(1 for _, _, confirmed, _ in persons_stats if confirmed)
        
        stats_text = f"Персон: {len(persons_stats)} | Подтверждено: {confirmed_persons} | Неопознанных лиц: {total_faces}"
        self.stats_label.setText(stats_text)
        
    def on_person_selected(self, index):
        """Обрабатывает выбор персоны"""
        person_id = self.persons_model.data(index, Qt.ItemDataRole.UserRole)
        self.current_person_id = person_id
        self.load_person_faces(person_id)
        
    def load_person_faces(self, person_id):
        """Загружает лица выбранной персоны"""
        # Очищаем текущие лица
        for i in reversed(range(self.faces_layout.count())):
            widget = self.faces_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
                
        faces = self.db_manager.get_person_faces(person_id)
        
        if not faces:
            no_faces_label = QLabel("Нет лиц для отображения")
            no_faces_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.faces_layout.addWidget(no_faces_label, 0, 0)
            return
            
        # Отображаем лица в сетке
        row, col = 0, 0
        max_cols = 4
        
        for face_id, image_id, image_path, x1, y1, x2, y2, confidence in faces:
            face_widget = FaceThumbnailWidget(
                face_id, image_path, (x1, y1, x2, y2), confidence
            )
            face_widget.face_confirmed.connect(self.on_face_confirmed)
            face_widget.face_rejected.connect(self.on_face_rejected)
            face_widget.face_double_clicked.connect(self.image_double_clicked)
            
            self.faces_layout.addWidget(face_widget, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
                
    def on_face_confirmed(self, face_id):
        """Обрабатывает подтверждение лица"""
        if self.current_person_id:
            if self.db_manager.confirm_person(self.current_person_id):
                QMessageBox.information(self, "Успех", "Персона подтверждена")
                self.refresh_data()
                
    def on_face_rejected(self, face_id):
        """Обрабатывает отклонение лица"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Убрать это лицо из персоны?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Перемещаем лицо обратно в "not recognized"
            not_recognized_id = self.db_manager.get_person_by_name('not recognized')
            if not_recognized_id:
                if self.db_manager.move_face_to_person(face_id, not_recognized_id):
                    QMessageBox.information(self, "Успех", "Лицо убрано из персоны")
                    self.refresh_data()
                    self.needs_refresh.emit()
                    
    def show_person_context_menu(self, position):
        """Показывает контекстное меню для персоны"""
        index = self.persons_list.indexAt(position)
        if index.isValid():
            person_id = self.persons_model.data(index, Qt.ItemDataRole.UserRole)
            person_name = self.persons_model.data(index, Qt.ItemDataRole.UserRole + 1)
            is_confirmed = self.persons_model.data(index, Qt.ItemDataRole.UserRole + 2)
            
            menu = QMenu(self)
            
            rename_action = QAction("Переименовать", self)
            rename_action.triggered.connect(lambda: self.rename_person(person_id, person_name))
            menu.addAction(rename_action)
            
            if not is_confirmed:
                confirm_action = QAction("Подтвердить", self)
                confirm_action.triggered.connect(lambda: self.confirm_person(person_id))
                menu.addAction(confirm_action)
                
            delete_action = QAction("Удалить персону", self)
            delete_action.triggered.connect(lambda: self.delete_person(person_id))
            menu.addAction(delete_action)
            
            menu.exec(self.persons_list.viewport().mapToGlobal(position))
            
    def rename_person(self, person_id, current_name):
        """Переименовывает персону"""
        dialog = PersonNameDialog(current_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.get_name()
            if new_name and new_name != current_name:
                if self.db_manager.update_person_name(person_id, new_name):
                    self.refresh_data()
                    self.needs_refresh.emit()
                    
    def confirm_person(self, person_id):
        """Подтверждает персону"""
        if self.db_manager.confirm_person(person_id):
            QMessageBox.information(self, "Успех", "Персона подтверждена")
            self.refresh_data()
            self.needs_refresh.emit()
            
    def delete_person(self, person_id):
        """Удаляет персону (перемещает все лица в not recognized)"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить персону? Все лица будут перемещены в 'not recognized'.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            not_recognized_id = self.db_manager.get_person_by_name('not recognized')
            if not_recognized_id:
                # Перемещаем все лица
                faces = self.db_manager.get_person_faces(person_id)
                for face_id, _, _, _, _, _, _, _ in faces:
                    self.db_manager.move_face_to_person(face_id, not_recognized_id)
                
                # Удаляем пустую персону
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM persons WHERE id = ?", (person_id,))
                    conn.commit()
                
                self.refresh_data()
                self.needs_refresh.emit()
                
    def cluster_faces(self):
        """Выполняет кластеризацию нераспознанных лиц"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Выполнить группировку нераспознанных лиц?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            progress = QProgressDialog("Группировка лиц...", "Отмена", 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            # Имитируем прогресс (в реальной реализации здесь будет настоящая кластеризация)
            for i in range(101):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                QApplication.processEvents()
                
            try:
                # Выполняем кластеризацию
                clusters = self.face_clusterer.cluster_faces()
                created_persons = self.face_clusterer.apply_clusters_to_database(clusters)
                
                progress.close()
                
                QMessageBox.information(
                    self, "Успех", 
                    f"Создано {created_persons} новых персон из {len(clusters)} кластеров"
                )
                
                self.refresh_data()
                self.needs_refresh.emit()
                
            except Exception as e:
                progress.close()
                QMessageBox.critical(self, "Ошибка", f"Ошибка при группировке: {e}")

from PyQt6.QtWidgets import QApplication