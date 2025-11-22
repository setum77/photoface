import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListView, QGridLayout, QPushButton, QMessageBox,
                             QMenu, QProgressDialog, QLabel, QLineEdit, 
                             QFileDialog, QScrollArea, QFrame, QSizePolicy,
                             QToolButton, QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QPixmap, QIcon, QFont
from src.photoface.core.database import DatabaseManager
from src.photoface.core.config import Config
from src.photoface.core.export_manager import ExportManager
from src.photoface.utils.helpers import generate_thumbnail, pil_to_pixmap

class AlbumThumbnailWidget(QFrame):
    """Виджет для отображения миниатюры фотографии в альбоме"""
    
    image_double_clicked = pyqtSignal(str)  # image_path
    
    def __init__(self, image_path, filename, is_group_photo=False, other_persons="", parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.filename = filename
        self.is_group_photo = is_group_photo
        self.other_persons = other_persons
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Миниатюра фотографии
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(150, 150)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet("border: 1px solid #ccc; background-color: white;")
        
        # Загружаем миниатюру
        self.load_thumbnail()
        
        # Информация о фотографии
        info_layout = QVBoxLayout()
        
        filename_label = QLabel(self.filename)
        filename_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        filename_label.setWordWrap(True)
        info_layout.addWidget(filename_label)
        
        if self.is_group_photo and self.other_persons:
            persons_label = QLabel(f"С: {self.other_persons}")
            persons_label.setStyleSheet("font-size: 9px; color: #666;")
            persons_label.setWordWrap(True)
            info_layout.addWidget(persons_label)
            
        elif self.is_group_photo:
            group_label = QLabel("Групповая фотография")
            group_label.setStyleSheet("font-size: 9px; color: #666;")
            info_layout.addWidget(group_label)
            
        layout.addWidget(self.thumbnail_label)
        layout.addLayout(info_layout)
        
        # Обработка двойного клика
        self.thumbnail_label.mouseDoubleClickEvent = self.thumbnail_double_clicked
        
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame { 
                border: 1px solid #ddd; 
                border-radius: 3px; 
                background-color: white;
            }
            QFrame:hover {
                border: 2px solid #0078d7;
                background-color: #f0f8ff;
            }
        """)
        
    def load_thumbnail(self):
        """Загружает миниатюру фотографии"""
        try:
            thumbnail = generate_thumbnail(self.image_path, size=(160, 160))
            if thumbnail:
                pixmap = pil_to_pixmap(thumbnail)
                self.thumbnail_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Ошибка загрузки миниатюры: {e}")
            
    def thumbnail_double_clicked(self, event):
        """Обрабатывает двойной клик на миниатюре"""
        self.image_double_clicked.emit(self.image_path)

class OutputPathDialog(QDialog):
    """Диалог для выбора пути экспорта"""
    
    def __init__(self, current_path="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выберите папку для альбомов")
        self.setModal(True)
        self.setFixedSize(500, 150)
        self.init_ui(current_path)
        
    def init_ui(self, current_path):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Папка для создания альбомов:"))
        
        path_layout = QHBoxLayout()
        
        self.path_edit = QLineEdit()
        self.path_edit.setText(current_path)
        self.path_edit.setPlaceholderText("Выберите папку для сохранения альбомов...")
        path_layout.addWidget(self.path_edit)
        
        self.browse_btn = QPushButton("Обзор...")
        self.browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.browse_btn)
        
        layout.addLayout(path_layout)
        
        # Информация
        info_label = QLabel("Для каждой подтвержденной персоны будет создана отдельная папка с фотографиями.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(info_label)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def browse_folder(self):
        """Открывает диалог выбора папки"""
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку для альбомов", self.path_edit.text()
        )
        if folder:
            self.path_edit.setText(folder)
            
    def get_path(self):
        return self.path_edit.text().strip()

class AlbumsTab(QWidget):
    """Вкладка для управления альбомами и экспорта"""
    
    image_double_clicked = pyqtSignal(str)
    needs_refresh = pyqtSignal()
    
    def __init__(self, db_manager: DatabaseManager, config: Config):
        super().__init__()
        self.db_manager = db_manager
        self.config = config
        self.export_manager = ExportManager(db_manager)
        self.current_person_id = None
        self.output_path = ""
        self.init_ui()
        self.connect_signals()
        
    # def init_ui(self):
    #     layout = QVBoxLayout(self)
        
    #     # Панель инструментов
    #     toolbar_layout = QHBoxLayout()
        
    #     self.output_path_btn = QPushButton("Конечная папка")
    #     self.output_path_btn.clicked.connect(self.set_output_path)
        
    #     self.sync_btn = QPushButton("Синхронизация")
    #     self.sync_btn.clicked.connect(self.start_sync)
    #     self.sync_btn.setEnabled(False)
        
    #     self.cancel_sync_btn = QPushButton("Отменить")
    #     self.cancel_sync_btn.clicked.connect(self.cancel_sync)
    #     self.cancel_sync_btn.setEnabled(False)
        
    #     self.refresh_btn = QPushButton("Обновить")
    #     self.refresh_btn.clicked.connect(self.refresh_data)
        
    #     self.stats_label = QLabel("Выберите конечную папку для начала работы")
        
    #     toolbar_layout.addWidget(self.output_path_btn)
    #     toolbar_layout.addWidget(self.sync_btn)
    #     toolbar_layout.addWidget(self.cancel_sync_btn)
    #     toolbar_layout.addWidget(self.refresh_btn)
    #     toolbar_layout.addWidget(self.stats_label)
    #     toolbar_layout.addStretch()
        
    #     layout.addLayout(toolbar_layout)
        
    #     # Основной разделитель
    #     splitter = QSplitter(Qt.Orientation.Horizontal)
        
    #     # Левая панель - список персон с альбомами
    #     self.left_panel = QWidget()
    #     left_layout = QVBoxLayout(self.left_panel)
        
    #     left_layout.addWidget(QLabel("Подтвержденные персоны:"))
        
    #     self.persons_list = QListView()
    #     self.persons_model = QStandardItemModel()
    #     self.persons_list.setModel(self.persons_model)
    #     self.persons_list.clicked.connect(self.on_person_selected)
    #     self.persons_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    #     self.persons_list.customContextMenuRequested.connect(self.show_person_context_menu)
        
    #     left_layout.addWidget(self.persons_list)
        
    #     # Информация о выбранной персоне
    #     self.person_info_label = QLabel("Выберите персону для просмотра фотографий")
    #     self.person_info_label.setWordWrap(True)
    #     self.person_info_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border: 1px solid #ddd;")
    #     left_layout.addWidget(self.person_info_label)
        
    #     splitter.addWidget(self.left_panel)
        
    #     # Правая панель - фотографии альбома
    #     self.right_panel = QWidget()
    #     right_layout = QVBoxLayout(self.right_panel)
        
    #     right_layout.addWidget(QLabel("Фотографии альбома:"))
        
    #     # Scroll area для миниатюр
    #     self.scroll_area = QScrollArea()
    #     self.photos_widget = QWidget()
    #     self.photos_layout = QGridLayout(self.photos_widget)
    #     self.photos_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
    #     self.scroll_area.setWidget(self.photos_widget)
    #     self.scroll_area.setWidgetResizable(True)
        
    #     right_layout.addWidget(self.scroll_area)
        
    #     splitter.addWidget(self.right_panel)
        
    #     # Установка пропорций
    #     splitter.setSizes([300, 900])
    #     layout.addWidget(splitter)
        
    #     # Прогресс-диалог
    #     self.progress_dialog = QProgressDialog("Синхронизация...", "Отменить", 0, 100, self)
    #     self.progress_dialog.setWindowTitle("Синхронизация альбомов")
    #     self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
    #     self.progress_dialog.canceled.connect(self.cancel_sync)
    #     self.progress_dialog.close()
        
    #     # Загружаем данные
    #     self.refresh_data()
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.output_path_btn = QPushButton("Конечная папка")
        self.output_path_btn.clicked.connect(self.set_output_path)
        
        self.sync_btn = QPushButton("Синхронизация")
        self.sync_btn.clicked.connect(self.start_sync)
        self.sync_btn.setEnabled(False)
        
        self.cancel_sync_btn = QPushButton("Отменить")
        self.cancel_sync_btn.clicked.connect(self.cancel_sync)
        self.cancel_sync_btn.setEnabled(False)
        
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        self.stats_label = QLabel("Выберите конечную папку для начала работы")
        
        toolbar_layout.addWidget(self.output_path_btn)
        toolbar_layout.addWidget(self.sync_btn)
        toolbar_layout.addWidget(self.cancel_sync_btn)
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addWidget(self.stats_label)
        toolbar_layout.addStretch()
        
        layout.addLayout(toolbar_layout)
        
        # Основной разделитель
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # Левая панель - список персон с альбомами
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("Подтвержденные персоны:"))
        
        self.persons_list = QListView()
        self.persons_model = QStandardItemModel()
        self.persons_list.setModel(self.persons_model)
        self.persons_list.clicked.connect(self.on_person_selected)
        self.persons_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.persons_list.customContextMenuRequested.connect(self.show_person_context_menu)
        
        left_layout.addWidget(self.persons_list)
        
        # Информация о выбранной персоне
        self.person_info_label = QLabel("Выберите персону для просмотра фотографий")
        self.person_info_label.setMaximumHeight(80)  # Ограничиваем высоту
        self.person_info_label.setWordWrap(True)
        self.person_info_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border: 1px solid #ddd;")
        left_layout.addWidget(self.person_info_label)
        
        splitter.addWidget(self.left_panel)
        
        # Правая панель - фотографии альбома
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        right_layout.addWidget(QLabel("Фотографии альбома:"))
        
        # Scroll area для миниатюр
        self.scroll_area = QScrollArea()
        self.photos_widget = QWidget()
        self.photos_layout = QGridLayout(self.photos_widget)
        self.photos_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.photos_widget)
        self.scroll_area.setWidgetResizable(True)
        
        right_layout.addWidget(self.scroll_area)
        
        splitter.addWidget(self.right_panel)
        
        # Установка пропорций
        splitter.setSizes([250, 650])
        layout.addWidget(splitter, 1)
        
    # def connect_signals(self):
    #     """Подключает сигналы экспорта"""
    #     self.export_manager.current_task.signals.progress_updated.connect(self.update_sync_progress)
    #     self.export_manager.current_task.signals.export_finished.connect(self.on_sync_finished)

    def connect_signals(self):
        """Подключает сигналы экспорта"""
        # Сигналы будут подключаться при создании задачи
        pass
        
    def refresh_data(self):
        """Обновляет данные в интерфейсе"""
        self.load_persons()
        self.update_stats()
        
    def load_persons(self):
        """Загружает список подтвержденных персон"""
        self.persons_model.clear()
        
        if not self.output_path:
            return
            
        persons = self.db_manager.get_persons_with_albums()
        
        for person_id, person_name, is_confirmed, output_path in persons:
            # Проверяем, создан ли альбом
            album_created = self.db_manager.is_album_created(person_id)
            
            display_name = person_name
            if album_created:
                display_name = f"✓ {display_name}"
                
            item = QStandardItem(display_name)
            item.setData(person_id, Qt.ItemDataRole.UserRole)
            item.setData(person_name, Qt.ItemDataRole.UserRole + 1)
            item.setData(album_created, Qt.ItemDataRole.UserRole + 2)
            
            if album_created:
                item.setForeground(Qt.GlobalColor.darkGreen)
                
            self.persons_model.appendRow(item)
            
    def update_stats(self):
        """Обновляет статистику"""
        if not self.output_path:
            self.stats_label.setText("Выберите конечную папку для начала работы")
            return
            
        persons = self.db_manager.get_persons_with_albums()
        total_persons = len(persons)
        created_albums = sum(1 for _, _, _, _ in persons if self.db_manager.is_album_created(_[0]))
        
        stats_text = f"Персон: {total_persons} | Создано альбомов: {created_albums}"
        self.stats_label.setText(stats_text)
        
    def on_person_selected(self, index):
        """Обрабатывает выбор персоны"""
        person_id = self.persons_model.data(index, Qt.ItemDataRole.UserRole)
        person_name = self.persons_model.data(index, Qt.ItemDataRole.UserRole + 1)
        album_created = self.persons_model.data(index, Qt.ItemDataRole.UserRole + 2)
        
        self.current_person_id = person_id
        self.load_person_photos(person_id, person_name, album_created)
        
    def load_person_photos(self, person_id, person_name, album_created):
        """Загружает фотографии выбранной персоны"""
        # Обновляем информацию о персоне
        photos = self.db_manager.get_person_photos(person_id)
        single_photos = self.db_manager.get_single_photos(person_id)
        group_photos = self.db_manager.get_photos_with_multiple_faces(person_id)
        
        info_text = (f"<b>{person_name}</b><br>"
                    f"Всего фотографий: {len(photos)}<br>"
                    f"Одиночных: {len(single_photos)}<br>"
                    f"С друзьями: {len(group_photos)}<br>"
                    f"Альбом: {'Создан' if album_created else 'Не создан'}")
        
        self.person_info_label.setText(info_text)
        
        # Очищаем текущие фотографии
        for i in reversed(range(self.photos_layout.count())):
            widget = self.photos_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
                
        if not photos:
            no_photos_label = QLabel("Нет фотографий для отображения")
            no_photos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.photos_layout.addWidget(no_photos_label, 0, 0)
            return
            
        # Отображаем одиночные фотографии
        if single_photos:
            single_label = QLabel("<b>Одиночные фотографии:</b>")
            single_label.setStyleSheet("margin-top: 10px; margin-bottom: 5px;")
            self.photos_layout.addWidget(single_label, 0, 0, 1, 4)
            
            row, col = 1, 0
            max_cols = 4
            
            for file_path, file_name, confidence in single_photos:
                photo_widget = AlbumThumbnailWidget(file_path, file_name, False)
                photo_widget.image_double_clicked.connect(self.image_double_clicked)
                self.photos_layout.addWidget(photo_widget, row, col)
                
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
                    
            row += 1  # Добавляем отступ
            
        # Отображаем групповые фотографии
        if group_photos:
            group_label = QLabel("<b>Фотографии с друзьями:</b>")
            group_label.setStyleSheet("margin-top: 10px; margin-bottom: 5px;")
            self.photos_layout.addWidget(group_label, row, 0, 1, 4)
            
            row += 1
            col = 0
            
            for file_path, file_name, other_persons in group_photos:
                photo_widget = AlbumThumbnailWidget(file_path, file_name, True, other_persons)
                photo_widget.image_double_clicked.connect(self.image_double_clicked)
                self.photos_layout.addWidget(photo_widget, row, col)
                
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
                    
    def show_person_context_menu(self, position):
        """Показывает контекстное меню для персоны"""
        index = self.persons_list.indexAt(position)
        if index.isValid():
            person_id = self.persons_model.data(index, Qt.ItemDataRole.UserRole)
            person_name = self.persons_model.data(index, Qt.ItemDataRole.UserRole + 1)
            
            menu = QMenu(self)
            
            sync_action = QAction("Синхронизировать альбом", self)
            sync_action.triggered.connect(lambda: self.start_sync(person_id))
            menu.addAction(sync_action)
            
            show_folder_action = QAction("Открыть папку альбома", self)
            show_folder_action.triggered.connect(lambda: self.show_album_folder(person_id))
            menu.addAction(show_folder_action)
            
            menu.exec(self.persons_list.viewport().mapToGlobal(position))
            
    def set_output_path(self):
        """Устанавливает путь для экспорта альбомов"""
        dialog = OutputPathDialog(self.output_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_path = dialog.get_path()
            
            if new_path and os.path.exists(new_path):
                self.output_path = new_path
                
                # Устанавливаем путь для всех подтвержденных персон
                persons = self.db_manager.get_all_persons(include_unconfirmed=False)
                for person_id, person_name, _, _ in persons:
                    self.db_manager.set_album_output_path(person_id, self.output_path)
                    
                self.sync_btn.setEnabled(True)
                self.refresh_data()
                QMessageBox.information(self, "Успех", f"Конечная папка установлена: {self.output_path}")
            else:
                QMessageBox.warning(self, "Ошибка", "Укажите существующую папку")
                
    # def start_sync(self, person_id=None):
    #     """Начинает синхронизацию альбомов"""
    #     if not self.output_path:
    #         QMessageBox.warning(self, "Ошибка", "Сначала выберите конечную папку")
    #         return
            
    #     if self.export_manager.is_exporting():
    #         QMessageBox.information(self, "Информация", "Синхронизация уже выполняется")
    #         return
            
    #     # Настройка UI для синхронизации
    #     self.sync_btn.setEnabled(False)
    #     self.cancel_sync_btn.setEnabled(True)
        
    #     # Запуск синхронизации
    #     if self.export_manager.start_export(person_id):
    #         self.progress_dialog.setValue(0)
    #         self.progress_dialog.show()
    #     else:
    #         QMessageBox.warning(self, "Ошибка", "Не удалось начать синхронизацию")
    #         self.on_sync_finished(False, "Ошибка запуска")

    def start_sync(self, person_id=None):
        """Начинает синхронизацию альбомов"""
        if not self.output_path:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите конечную папку")
            return
            
        if self.export_manager.is_exporting():
            QMessageBox.information(self, "Информация", "Синхронизация уже выполняется")
            return
            
        # Настройка UI для синхронизации
        self.sync_btn.setEnabled(False)
        self.cancel_sync_btn.setEnabled(True)
        
        # Запуск синхронизации
        if self.export_manager.start_export(person_id):
            # Подключаем сигналы к текущей задаче
            task = self.export_manager.current_task
            task.signals.progress_updated.connect(self.update_sync_progress)
            task.signals.export_finished.connect(self.on_sync_finished)
            
            self.progress_dialog.setValue(0)
            self.progress_dialog.show()
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось начать синхронизацию")
            self.on_sync_finished(False, "Ошибка запуска")
            
    def cancel_sync(self):
        """Отменяет текущую синхронизацию"""
        self.export_manager.cancel_export()
        self.on_sync_finished(False, "Синхронизация отменена")
        
    def update_sync_progress(self, current, total, description):
        """Обновляет прогресс синхронизации"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_dialog.setValue(progress)
            self.progress_dialog.setLabelText(f"Синхронизация: {description}")
            
    def on_sync_finished(self, success, message):
        """Обрабатывает завершение синхронизации"""
        self.sync_btn.setEnabled(True)
        self.cancel_sync_btn.setEnabled(False)
        self.progress_dialog.hide()
        
        if success:
            QMessageBox.information(self, "Успех", message)
        else:
            QMessageBox.warning(self, "Предупреждение", message)
            
        self.refresh_data()
        self.needs_refresh.emit()
        
    def show_album_folder(self, person_id):
        """Открывает папку альбома в проводнике"""
        album_path = self.db_manager.get_album_output_path(person_id)
        if album_path and os.path.exists(album_path):
            person_name = None
            persons = self.db_manager.get_persons_with_albums()
            for pid, pname, _, _ in persons:
                if pid == person_id:
                    person_name = pname
                    break
                    
            if person_name:
                full_album_path = os.path.join(album_path, person_name)
                if os.path.exists(full_album_path):
                    os.startfile(full_album_path)
                else:
                    QMessageBox.information(self, "Информация", "Альбом еще не создан")
            else:
                QMessageBox.warning(self, "Ошибка", "Персона не найдена")
        else:
            QMessageBox.warning(self, "Ошибка", "Альбом не настроен или папка не существует")

from PyQt6.QtWidgets import QApplication