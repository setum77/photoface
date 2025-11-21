from PyQt6.QtWidgets import QMainWindow, QTabWidget
from src.photoface.core.database import DatabaseManager
from .folders_tab import FoldersTab

class MainWindow(QMainWindow):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Photo Face Manager")
        self.setGeometry(100, 100, 1200, 800)

        # Центральный виджет с вкладками
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Создание вкладок
        self.folders_tab = FoldersTab(self.db_manager)
        self.faces_tab = self._create_faces_tab()
        self.albums_tab = self._create_albums_tab()

        self.tabs.addTab(self.folders_tab, "Папки")
        self.tabs.addTab(self.faces_tab, "Лица")
        self.tabs.addTab(self.albums_tab, "Альбомы")

        # Подключаем сигналы
        self.folders_tab.image_double_clicked.connect(self.show_fullscreen_image)

    def _create_faces_tab(self):
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Вкладка 'Лица' - будет реализована в Этапе 4"))
        return tab

    def _create_albums_tab(self):
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Вкладка 'Альбомы' - будет реализована в Этапе 6"))
        return tab

    def show_fullscreen_image(self, image_path):
        """Показывает изображение в полноэкранном режиме"""
        # TODO: Реализовать в Этапе 5
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Полноэкранный просмотр", 
                               f"Будет открыто: {image_path}\n(реализовано в Этапе 5)")