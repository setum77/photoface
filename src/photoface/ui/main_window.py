from PyQt6.QtWidgets import QMainWindow, QTabWidget
from src.photoface.core.database import DatabaseManager
from .folders_tab import FoldersTab
from .faces_tab import FacesTab
from .albums_tab import AlbumsTab
from .photo_viewer import FullScreenPhotoViewer


class MainWindow(QMainWindow):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self.photo_viewer = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Photo Face Manager")
        self.setGeometry(100, 100, 1200, 800)

        # Центральный виджет с вкладками
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Создание вкладок
        self.folders_tab = FoldersTab(self.db_manager)
        self.faces_tab = FacesTab(self.db_manager)
        self.albums_tab = AlbumsTab(self.db_manager)

        self.tabs.addTab(self.folders_tab, "Папки")
        self.tabs.addTab(self.faces_tab, "Лица")
        self.tabs.addTab(self.albums_tab, "Альбомы")

        # Подключаем сигналы
        self.folders_tab.image_double_clicked.connect(self.show_fullscreen_image)
        self.faces_tab.image_double_clicked.connect(self.show_fullscreen_image)
        self.albums_tab.image_double_clicked.connect(self.show_fullscreen_image)
        
        self.faces_tab.needs_refresh.connect(self.on_faces_refresh)
        self.albums_tab.needs_refresh.connect(self.on_albums_refresh)

    def show_fullscreen_image(self, image_path):
        """Показывает изображение в полноэкранном режиме"""
        # Закрываем предыдущий просмотрщик если есть
        if self.photo_viewer:
            self.photo_viewer.close()
            
        # Создаем новый просмотрщик
        self.photo_viewer = FullScreenPhotoViewer(self.db_manager, self)
        self.photo_viewer.closed.connect(self.on_photo_viewer_closed)
        
        # Показываем изображение
        if self.photo_viewer.show_image(image_path):
            # Скрываем главное окно
            self.hide()
        else:
            self.photo_viewer = None

    def on_photo_viewer_closed(self):
        """Обрабатывает закрытие просмотрщика"""
        if self.photo_viewer:
            self.photo_viewer.deleteLater()
            self.photo_viewer = None
            
        # Показываем главное окно
        self.show()
        self.raise_()
        self.activateWindow()

    def on_faces_refresh(self):
        """Обновляет данные при изменениях во вкладке Лица"""
        # Обновляем вкладку Альбомы при изменении лиц
        self.albums_tab.refresh_data()

    def on_albums_refresh(self):
        """Обновляет данные при изменениях во вкладке Альбомы"""
        # Можно добавить обновление других вкладок при необходимости
        pass