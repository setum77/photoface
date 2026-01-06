from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QMessageBox, QMenu, 
                             QStatusBar, QApplication)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QCloseEvent, QAction
from src.photoface.core.database import DatabaseManager
from src.photoface.core.config import Config
from .folders_tab import FoldersTab
from .faces_tab import FacesTab
from .albums_tab import AlbumsTab
from .photo_viewer import PhotoViewerWindow
from .settings_dialog import SettingsDialog

class MainWindow(QMainWindow):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self.config = Config(db_manager)
        self.photo_viewer = None
        self.init_ui()
        self.load_window_state()
        
    def init_ui(self):
        self.setWindowTitle("Photo Face Manager")
        self.setGeometry(100, 100, 1200, 800)
        
        # Устанавливаем иконку приложения
        from PyQt6.QtGui import QIcon
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        # Также устанавливаем иконку для приложения в целом
        QApplication.instance().setWindowIcon(QIcon(icon_path))

        # Создание меню
        self.create_menu()
        
        # Создание статусной строки
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе")

        # Центральный виджет с вкладками
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Создание вкладок
        self.folders_tab = FoldersTab(self.db_manager, self.config)
        self.faces_tab = FacesTab(self.db_manager, self.config)
        self.albums_tab = AlbumsTab(self.db_manager, self.config)

        self.tabs.addTab(self.folders_tab, "Папки")
        self.tabs.addTab(self.faces_tab, "Лица")
        self.tabs.addTab(self.albums_tab, "Альбомы")

        # Подключаем сигналы
        self.folders_tab.image_double_clicked.connect(self.show_fullscreen_image)
        self.faces_tab.image_double_clicked.connect(self.show_fullscreen_image)
        self.albums_tab.image_double_clicked.connect(self.show_fullscreen_image)
        
        self.faces_tab.needs_refresh.connect(self.on_faces_refresh)
        self.albums_tab.needs_refresh.connect(self.on_albums_refresh)
        
        # Восстанавливаем последнюю вкладку
        last_tab = self.config.get('ui.last_tab_index', 0)
        if last_tab < self.tabs.count():
            self.tabs.setCurrentIndex(last_tab)

    def create_menu(self):
        """Создает главное меню"""
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu('Файл')
        
        settings_action = QAction('Настройки', self)
        settings_action.setShortcut('Ctrl+,')
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Выход', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню Вид
        view_menu = menubar.addMenu('Вид')
        
        fullscreen_action = QAction('Полный экран', self)
        fullscreen_action.setShortcut('F11')
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # Меню Справка
        help_menu = menubar.addMenu('Справка')
        
        about_action = QAction('О программе', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_settings(self):
        """Показывает диалог настроек"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # Применяем изменения настроек
            self.apply_config_changes()
            
    def apply_config_changes(self):
        """Применяет изменения конфигурации"""
        # Здесь можно добавить логику применения настроек в реальном времени
        self.status_bar.showMessage("Настройки применены", 3000)
        
        # Обновляем конфигурацию в scan_manager
        if hasattr(self.folders_tab, 'scan_manager'):
            self.folders_tab.scan_manager.update_config(self.config)
            
    def apply_config_changes(self):
        """Применяет изменения конфигурации"""
        # Здесь можно добавить логику применения настроек в реальном времени
        self.status_bar.showMessage("Настройки применены", 3000)
        
    def toggle_fullscreen(self):
        """Переключает полноэкранный режим"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
            
    def show_about(self):
        """Показывает информацию о программе"""
        about_text = """
        <h2>Photo Face Manager</h2>
        <p>Версия 1.0.0</p>
        <p>Программа для управления фотографиями с распознаванием лиц.</p>
        <p>Основные возможности:</p>
        <ul>
            <li>Распознавание и группировка лиц</li>
            <li>Управление коллекцией фотографий</li>
            <li>Создание тематических альбомов</li>
            <li>Экспорт упорядоченных коллекций</li>
        </ul>
        <p>© 2024 Photo Face Manager</p>
        """
        QMessageBox.about(self, "О программе", about_text)
        
    def load_window_state(self):
        """Загружает состояние окна"""
        geometry = self.config.get('ui.window_geometry')
        if geometry:
            # Преобразуем строку в bytes, если необходимо
            if isinstance(geometry, str):
                try:
                    # Попробуем десериализовать JSON строку, если она содержит закодированные байты
                    import json
                    parsed = json.loads(geometry)
                    if isinstance(parsed, dict) and parsed.get("__type__") == "QByteArray":
                        import base64
                        encoded = parsed["__value__"]
                        geometry = base64.b64decode(encoded.encode('ascii'))
                except (json.JSONDecodeError, KeyError, TypeError):
                    # Если не удалось десериализовать, оставляем как есть
                    pass
            
            # Проверяем тип данных перед вызовом restoreGeometry
            if isinstance(geometry, (bytes, bytearray)):
                self.restoreGeometry(geometry)
            elif hasattr(geometry, 'data'):  # QByteArray
                self.restoreGeometry(geometry)
            
        state = self.config.get('ui.window_state')
        if state:
            # Аналогичная проверка для состояния окна
            if isinstance(state, str):
                try:
                    import json
                    parsed = json.loads(state)
                    if isinstance(parsed, dict) and parsed.get("__type__") == "QByteArray":
                        import base64
                        encoded = parsed["__value__"]
                        state = base64.b64decode(encoded.encode('ascii'))
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
            
            if isinstance(state, (bytes, bytearray)):
                self.restoreState(state)
            elif hasattr(state, 'data'):  # QByteArray
                self.restoreState(state)
            
    def save_window_state(self):
        """Сохраняет состояние окна"""
        # Сохраняем геометрию и состояние как QByteArray объекты
        geometry = self.saveGeometry()
        state = self.saveState()
        
        # Сохраняем в конфигурацию
        self.config.set('ui.window_geometry', geometry)
        self.config.set('ui.window_state', state)
        self.config.set('ui.last_tab_index', self.tabs.currentIndex())
        
    def closeEvent(self, event: QCloseEvent):
        """Обрабатывает закрытие окна"""
        self.save_window_state()
        
        # Закрываем просмотрщик если открыт
        if self.photo_viewer:
            self.photo_viewer.close()
            
        event.accept()

    # def show_fullscreen_image(self, image_path):
    #     """Показывает изображение в полноэкранном режиме"""
    #     print(f"Запрос на показ изображения: {image_path}")  # Отладочная информация

    #     # Закрываем предыдущий просмотрщик если есть
    #     if self.photo_viewer:
    #         self.photo_viewer.close()
    #         self.photo_viewer = None
            
    #     # Создаем новый просмотрщик
    #     self.photo_viewer = FullScreenPhotoViewer(self.db_manager, self.config, self)
    #     self.photo_viewer.closed.connect(self.on_photo_viewer_closed)
        
    #     # Показываем изображение
    #     if self.photo_viewer.show_image(image_path):
    #         # Скрываем главное окно
    #         self.hide()
    #     else:
    #         self.photo_viewer = None
    # def show_fullscreen_image(self, image_path):
    #     """Показывает изображение в полноэкранном режиме"""
    #     print(f"Запрос на показ изображения: {image_path}")  # Отладочная информация
        
    #     # Закрываем предыдущий просмотрщик если есть
    #     if self.photo_viewer:
    #         self.photo_viewer.close()
    #         self.photo_viewer = None
            
    #     # Создаем новый просмотрщик
    #     self.photo_viewer = FullScreenPhotoViewer(self.db_manager, self.config, self)
    #     self.photo_viewer.closed.connect(self.on_photo_viewer_closed)
        
    #     # Показываем изображение
    #     if self.photo_viewer.show_image(image_path):
    #         print("Изображение показано, скрываем главное окно")  # Отладочная информация
    #         # Скрываем главное окно
    #         self.hide()
    #     else:
    #         print("Не удалось показать изображение")  # Отладочная информация
    #         self.photo_viewer = None
    #         QMessageBox.warning(self, "Ошибка", "Не удалось открыть изображение")
    def show_fullscreen_image(self, image_path):
        """Показывает изображение в отдельном окне"""
        print(f"Запрос на показ изображения: {image_path}")
        
        # Закрываем предыдущий просмотрщик если есть
        if self.photo_viewer:
            self.photo_viewer.close()
            self.photo_viewer = None
        
        # Создаем новый просмотрщик как отдельное окно
        self.photo_viewer = PhotoViewerWindow(self.db_manager, self.config)
        self.photo_viewer.closed.connect(self.on_photo_viewer_closed)
        
        # Показываем изображение
        if self.photo_viewer.show_image(image_path):
            print("Изображение показано в отдельном окне")
            # НЕ скрываем главное окно - оставляем оба окна видимыми
            # self.hide()  # ЗАКОММЕНТИРУЙТЕ ЭТУ СТРОКУ
        else:
            print("Не удалось показать изображение")
            self.photo_viewer = None
            QMessageBox.warning(self, "Ошибка", "Не удалось открыть изображение")

    def on_photo_viewer_closed(self):
        """Обрабатывает закрытие просмотрщика"""
        if self.photo_viewer:
            self.photo_viewer.deleteLater()
            self.photo_viewer = None
        
        # Убедимся, что главное окно видимо
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