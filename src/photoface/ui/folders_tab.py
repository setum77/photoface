import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QTreeView, QListView, QPushButton, QFileDialog,
                             QMessageBox, QMenu, QProgressDialog, QLabel, QApplication)
from PyQt6.QtCore import QDir, QModelIndex, Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFileSystemModel, QAction, QStandardItemModel, QStandardItem, QIcon
from src.photoface.core.database import DatabaseManager
from src.photoface.core.scan_manager import ScanManager
from src.photoface.core.config import Config
from src.photoface.utils.helpers import generate_thumbnail, pil_to_pixmap, get_image_files

class ThumbnailListModel(QStandardItemModel):
    """Модель для отображения миниатюр фотографий"""
    def __init__(self):
        super().__init__()

class FoldersTab(QWidget):
    # Сигналы для связи с другими компонентами
    folder_selected = pyqtSignal(str)
    image_double_clicked = pyqtSignal(str)
    scan_progress_updated = pyqtSignal(int, int, str)
    scan_finished = pyqtSignal()

    def __init__(self, db_manager: DatabaseManager, config: Config):
        super().__init__()
        self.db_manager = db_manager
        self.config = config
        self.scan_manager = ScanManager(db_manager)
        self.current_folder = None
        self.current_folder_id = None
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # Уменьшаем отступы
        layout.setSpacing(5)  # Уменьшаем расстояние между элементами

        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.add_folder_btn = QPushButton("Добавить папку")
        self.add_folder_btn.clicked.connect(self.add_folder)
        
        self.remove_folder_btn = QPushButton("Удалить папку")
        self.remove_folder_btn.clicked.connect(self.remove_selected_folder)
        
        self.scan_btn = QPushButton("Начать сканирование")
        self.scan_btn.clicked.connect(self.start_scanning)

        self.cancel_scan_btn = QPushButton("Отменить сканирование")
        self.cancel_scan_btn.clicked.connect(self.cancel_scanning)
        self.cancel_scan_btn.setEnabled(False)
        
        self.editor_btn = QPushButton("Внешний редактор")
        self.editor_btn.clicked.connect(self.set_external_editor)

        # Временная кнопка для очистки данных
        self.clear_btn = QPushButton("Очистить данные")
        self.clear_btn.clicked.connect(self.clear_data)

        toolbar_layout.addWidget(self.add_folder_btn)
        toolbar_layout.addWidget(self.remove_folder_btn)
        toolbar_layout.addWidget(self.scan_btn)
        toolbar_layout.addWidget(self.cancel_scan_btn)
        toolbar_layout.addWidget(self.editor_btn)
        toolbar_layout.addWidget(self.clear_btn)
        toolbar_layout.addStretch()
        
        # Статус сканирования
        self.status_label = QLabel("Готов к сканированию")
        toolbar_layout.addWidget(self.status_label)

        layout.addLayout(toolbar_layout)

        # Основной разделитель
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)  # Не позволяем панелям схлопываться

        # Левая панель - дерево папок
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("Добавленные папки:"))
        
        # Модель для отображения добавленных папок
        self.folders_model = QStandardItemModel()
        self.folders_tree = QTreeView()
        self.folders_tree.setModel(self.folders_model)
        self.folders_tree.setHeaderHidden(True)
        self.folders_tree.doubleClicked.connect(self.on_folder_double_clicked)
        
        # Контекстное меню для папок
        self.folders_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folders_tree.customContextMenuRequested.connect(self.show_folder_context_menu)
        
        left_layout.addWidget(self.folders_tree)

        # Статистика папки
        self.folder_stats_label = QLabel("Выберите папку для просмотра статистики")
        self.folder_stats_label.setMaximumHeight(60)  # Ограничиваем высоту
        left_layout.addWidget(self.folder_stats_label)
        
        splitter.addWidget(self.left_panel)

        # Правая панель - миниатюры
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        right_layout.addWidget(QLabel("Фотографии:"))
        
        # Список для миниатюр
        self.thumbnails_model = ThumbnailListModel()
        self.thumbnails_view = QListView()
        self.thumbnails_view.setModel(self.thumbnails_model)
        self.thumbnails_view.setViewMode(QListView.ViewMode.IconMode)
        self.thumbnails_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.thumbnails_view.setGridSize(QSize(150, 150))
        self.thumbnails_view.setIconSize(QSize(120, 120))
        self.thumbnails_view.doubleClicked.connect(self.on_image_double_clicked)
        
        right_layout.addWidget(self.thumbnails_view)
        
        splitter.addWidget(self.right_panel)

        # Установка пропорций (увеличиваем правую панель)
        splitter.setSizes([200, 600])
        layout.addWidget(splitter, 1)  # 1 - коэффициент растяжения

        # Прогресс-диалог
        self.progress_dialog = QProgressDialog("Сканирование...", "Отменить", 0, 100, self)
        self.progress_dialog.setWindowTitle("Сканирование фотографий")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_scanning)
        self.progress_dialog.close()

        # Загружаем добавленные папки
        self.load_folders()
    
    def connect_signals(self):
        """Подключает сигналы сканирования"""
        self.scan_progress_updated.connect(self.update_scan_progress)
        self.scan_finished.connect(self.on_scan_finished)

    def load_folders(self):
        """Загружает список добавленных папок из базы данных"""
        self.folders_model.clear()
        folders = self.db_manager.get_all_folders()
        
        for folder_id, folder_path, added_date in folders:
            item = QStandardItem(folder_path)
            item.setData(folder_id, Qt.ItemDataRole.UserRole + 1)  # ID папки
            item.setData(folder_path, Qt.ItemDataRole.UserRole)    # Путь папки
            self.folders_model.appendRow(item)

    def update_folder_stats(self, folder_id, folder_path):
        """Обновляет статистику выбранной папки"""
        try:
            total_images = len(get_image_files(folder_path))
            processed_images = self.db_manager.get_processed_images_count(folder_id)
            
            stats_text = (f"Папка: {os.path.basename(folder_path)}\n"
                         f"Всего изображений: {total_images}\n"
                         f"Обработано: {processed_images}\n"
                         f"Осталось: {total_images - processed_images}")
            
            self.folder_stats_label.setText(stats_text)
            
        except Exception as e:
            self.folder_stats_label.setText(f"Ошибка загрузки статистики: {e}")

    def add_folder(self):
        """Добавляет новую папку для обработки"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Выберите папку с фотографиями"
        )
        
        if folder_path:
            # Нормализуем путь
            folder_path = os.path.normpath(folder_path)
            
            if self.db_manager.add_folder(folder_path):
                self.load_folders()
                QMessageBox.information(self, "Успех", f"Папка добавлена: {folder_path}")
            else:
                QMessageBox.warning(self, "Ошибка", "Папка уже добавлена или произошла ошибка")

    def remove_selected_folder(self):
        """Удаляет выбранную папку из обработки"""
        selected_indexes = self.folders_tree.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Внимание", "Выберите папку для удаления")
            return
        
        index = selected_indexes[0]
        folder_path = self.folders_model.data(index, Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Подтверждение", 
            f"Удалить папку '{folder_path}' из обработки?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.db_manager.remove_folder(folder_path):
                self.load_folders()
                self.thumbnails_model.clear()  # Очищаем миниатюры
                self.folder_stats_label.setText("Выберите папку для просмотра статистики")
                QMessageBox.information(self, "Успех", "Папка удалена из обработки")

    def show_folder_context_menu(self, position):
        """Показывает контекстное меню для папки"""
        index = self.folders_tree.indexAt(position)
        if index.isValid():
            menu = QMenu(self)

            remove_action = QAction("Удалить из обработки", self)
            remove_action.triggered.connect(self.remove_selected_folder)
            menu.addAction(remove_action)
            
            scan_action = QAction("Сканировать эту папку", self)
            scan_action.triggered.connect(lambda: self.start_scanning(selected_folder=True))
            menu.addAction(scan_action)
            
            menu.exec(self.folders_tree.viewport().mapToGlobal(position))

    def on_folder_double_clicked(self, index):
        """Обрабатывает двойной клик на папке - загружает фотографии"""
        folder_path = self.folders_model.data(index, Qt.ItemDataRole.UserRole)
        folder_id = self.folders_model.data(index, Qt.ItemDataRole.UserRole + 1)
        
        self.current_folder = folder_path
        self.current_folder_id = folder_id
        self.load_folder_images(folder_path)
        self.update_folder_stats(folder_id, folder_path)

    def load_folder_images(self, folder_path):
        """Загружает фотографии из выбранной папки"""
        if not os.path.exists(folder_path):
            QMessageBox.warning(self, "Ошибка", "Папка не существует")
            return
        
        self.current_folder = folder_path
        self.thumbnails_model.clear()
        
        # Получаем список файлов изображений
        image_files = get_image_files(folder_path)
        
        if not image_files:
            QMessageBox.information(self, "Информация", "В папке нет изображений")
            return
        
        # Показываем прогресс-диалог для больших папок
        progress = QProgressDialog("Загрузка миниатюр...", "Отмена", 0, len(image_files), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        for i, image_path in enumerate(image_files):
            if progress.wasCanceled():
                break
                
            progress.setValue(i)
            progress.setLabelText(f"Загрузка: {os.path.basename(image_path)}")
            
            # Генерируем миниатюру
            thumbnail = generate_thumbnail(image_path)
            if thumbnail:
                pixmap = pil_to_pixmap(thumbnail)
                item = QStandardItem()
                item.setIcon(QIcon(pixmap))
                item.setText(os.path.basename(image_path))
                item.setData(image_path, Qt.ItemDataRole.UserRole)
                self.thumbnails_model.appendRow(item)
            
            QApplication.processEvents()  # Для отзывчивости UI
        
        progress.setValue(len(image_files))

    def on_image_double_clicked(self, index):
        """Обрабатывает двойной клик на изображении"""
        image_path = self.thumbnails_model.data(index, Qt.ItemDataRole.UserRole)
        if image_path:
            self.image_double_clicked.emit(image_path)

    def start_scanning(self, selected_folder=False):
        """Начинает сканирование папок на распознавание лиц"""
        if self.scan_manager.is_scanning():
            QMessageBox.information(self, "Информация", "Сканирование уже выполняется")
            return
        
        folder_id = None
        if selected_folder:
            # Сканировать только выбранную папку
            selected_indexes = self.folders_tree.selectedIndexes()
            if not selected_indexes:
                QMessageBox.warning(self, "Внимание", "Выберите папку для сканирования")
                return
            index = selected_indexes[0]
            folder_id = self.folders_model.data(index, Qt.ItemDataRole.UserRole + 1)
        
        # Настройка UI для сканирования
        self.scan_btn.setEnabled(False)
        self.cancel_scan_btn.setEnabled(True)
        self.status_label.setText("Сканирование...")
        
        # Запуск сканирования
        if self.scan_manager.start_scan(folder_id):
            # Подключаем сигналы к текущей задаче
            task = self.scan_manager.current_task
            task.signals.progress_updated.connect(self.scan_progress_updated)
            task.signals.scan_finished.connect(self.scan_finished)
            task.signals.error_occurred.connect(self.on_scan_error)
            
            # Показываем прогресс-диалог
            self.progress_dialog.setValue(0)
            self.progress_dialog.show()
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось начать сканирование")

    def cancel_scanning(self):
        """Отменяет текущее сканирование"""
        self.scan_manager.cancel_scan()
        self.on_scan_finished()
        QMessageBox.information(self, "Информация", "Сканирование отменено")

    def update_scan_progress(self, current, total, filename):
        """Обновляет прогресс сканирования"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_dialog.setValue(progress)
            self.progress_dialog.setLabelText(f"Обработка: {filename}")
        
        self.status_label.setText(f"Сканирование... {current}/{total}")

    def on_scan_finished(self):
        """Обрабатывает завершение сканирования"""
        self.scan_btn.setEnabled(True)
        self.cancel_scan_btn.setEnabled(False)
        self.status_label.setText("Сканирование завершено")
        self.progress_dialog.hide()
        
        # Обновляем статистику если папка выбрана
        if self.current_folder_id:
            self.update_folder_stats(self.current_folder_id, self.current_folder)
        
        QMessageBox.information(self, "Успех", "Сканирование завершено!")

    def on_scan_error(self, error_message):
        """Обрабатывает ошибки сканирования"""
        self.on_scan_finished()
        QMessageBox.critical(self, "Ошибка сканирования", f"Произошла ошибка: {error_message}")

    def set_external_editor(self):
        """Устанавливает внешний редактор изображений"""
        editor_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите программу для редактирования изображений"
        )
        if editor_path:
            QMessageBox.information(self, "Успех", f"Редактор установлен: {editor_path}")

    def clear_data(self):
        """Очищает все обработанные данные"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Очистить все обработанные данные?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.db_manager.clear_processed_data()
            QMessageBox.information(self, "Успех", "Данные очищены")
            self.load_folders()

# from PyQt6.QtWidgets import QApplication
# from PyQt6.QtCore import QSize