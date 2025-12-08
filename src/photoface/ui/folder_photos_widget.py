import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QPushButton, QLabel, QFrame, QSizePolicy, QListView)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QPixmap, QIcon, QFont
from src.photoface.utils.helpers import generate_thumbnail, pil_to_pixmap, get_image_files


class FolderPhotoWidget(QFrame):
    """Виджет для отображения миниатюры фотографии"""
    
    photo_double_clicked = pyqtSignal(str)  # image_path
    
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Миниатюра фотографии
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(120, 120)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet("border: 1px solid #ccc; background-color: white;")
        
        # Загружаем миниатюру
        self.load_thumbnail()
        
        layout.addWidget(self.thumbnail_label)
        
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 3px; }")
        
        # Устанавливаем политику фокуса и включаем обработку двойного клика
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
    def load_thumbnail(self):
        """Загружает миниатюру фотографии"""
        try:
            thumbnail = generate_thumbnail(self.image_path)
            if thumbnail:
                pixmap = pil_to_pixmap(thumbnail)
                self.thumbnail_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Error loading thumbnail for {self.image_path}: {e}")
            
    def mouseDoubleClickEvent(self, event):
        """Обработка двойного клика по миниатюре"""
        self.photo_double_clicked.emit(self.image_path)


class FolderPhotosBlockWidget(QWidget):
    """Виджет блока папки с заголовком и миниатюрами фотографий"""
    
    scan_folder = pyqtSignal(str) # folder_path
    delete_folder = pyqtSignal(str) # folder_path
    folder_selected = pyqtSignal(str) # folder_path
    photo_double_clicked = pyqtSignal(str) # image_path
    
    def __init__(self, folder_path, folder_id, db_manager, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.folder_id = folder_id
        self.db_manager = db_manager
        self.photo_widgets = []
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header - содержит имя папки и управляющие кнопки
        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(80)  # Фиксированная высота 80px
        self.header_widget.setStyleSheet("background-color: rgb(200, 200, 200);")  # Серый фон
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)
        
        # Контейнер для информации о папке
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(50, 0, 0, 0)  # Отступ 50px от левого края
        
        # Имя папки с количеством фотографий
        image_files = get_image_files(self.folder_path)
        self.name_label = QLabel(f"{os.path.basename(self.folder_path)} ({len(image_files)} фотографий)")
        font = self.name_label.font()
        font.setBold(True)
        font.setPointSize(22)  # Размер шрифта 22 пункта
        self.name_label.setFont(font)
        
        # Определяем, сканировалась ли папка
        processed_images = self.db_manager.get_processed_images_count(self.folder_id)
        if processed_images > 0:
            self.name_label.setStyleSheet("color: rgb(0, 140, 16);")  # Зеленый цвет
        else:
            self.name_label.setStyleSheet("color: rgb(0, 0, 140);")  # Синий цвет
            
        info_layout.addWidget(self.name_label)
        
        # Путь к папке мелким шрифтом
        path_label = QLabel(self.folder_path)
        path_label.setStyleSheet("font-size: 12px; color: #666;")
        path_label.setWordWrap(True)
        info_layout.addWidget(path_label)
        
        header_layout.addWidget(info_container)
        
        # Контейнер для кнопок, чтобы выровнять их по правому краю
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        # Кнопка "Сканировать папку"
        scan_btn = QPushButton("Сканировать папку")
        scan_btn.clicked.connect(lambda: self.scan_folder.emit(self.folder_path))
        buttons_layout.addWidget(scan_btn)
        
        # Кнопка "Удалить папку"
        delete_btn = QPushButton("Удалить папку")
        delete_btn.clicked.connect(lambda: self.delete_folder.emit(self.folder_path))
        buttons_layout.addWidget(delete_btn)
        
        header_layout.addWidget(buttons_container)
        
        main_layout.addWidget(self.header_widget)
        
        # Body - содержит миниатюры фотографий
        self.body_widget = QWidget()
        self.body_widget.setStyleSheet("background-color: white;")  # Белый фон
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(5, 5, 5, 5)
        
        # Сетка для миниатюр фотографий
        self.photos_layout = QGridLayout()
        self.photos_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Добавляем миниатюры фотографий
        image_files = get_image_files(self.folder_path)
        row, col = 0, 0
        max_cols = 4
        
        for image_path in image_files:
            photo_widget = FolderPhotoWidget(image_path)
            photo_widget.photo_double_clicked.connect(self.on_photo_double_clicked)
            self.photos_layout.addWidget(photo_widget, row, col)
            self.photo_widgets.append(photo_widget)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        body_layout.addLayout(self.photos_layout)
        
        main_layout.addWidget(self.body_widget)
        
        # Устанавливаем политику размера
        self.header_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.body_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
    def on_photo_double_clicked(self, image_path):
        """Обработка двойного клика по фотографии"""
        self.photo_double_clicked.emit(image_path)
        
    def mousePressEvent(self, event):
        """Обработка клика по блоку папки"""
        super().mousePressEvent(event)
        # Вызываем сигнал выбора папки
        self.folder_selected.emit(self.folder_path)