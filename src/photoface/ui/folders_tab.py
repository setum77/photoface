import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QTreeView, QListView, QPushButton, QFileDialog,
                             QMessageBox, QMenu, QProgressDialog, QLabel, QApplication,
                             QScrollArea, QFrame)
from PyQt6.QtCore import QDir, QModelIndex, Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFileSystemModel, QAction, QStandardItemModel, QStandardItem, QIcon
from src.photoface.core.database import DatabaseManager
from src.photoface.core.scan_manager import ScanManager
from src.photoface.core.config import Config
from src.photoface.utils.helpers import generate_thumbnail, pil_to_pixmap, get_image_files
from src.photoface.ui.folder_photos_widget import FolderPhotosBlockWidget

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
        self.scan_manager = ScanManager(db_manager, config)
        self.current_folder = None
        self.current_folder_id = None
        self.folder_blocks = {}  # Словарь для хранения блоков папок
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
        
        self.scan_btn = QPushButton("Начать сканирование")
        self.scan_btn.clicked.connect(self.start_scanning)

        self.cancel_scan_btn = QPushButton("Отменить сканирование")
        self.cancel_scan_btn.clicked.connect(self.cancel_scanning)
        self.cancel_scan_btn.setEnabled(False)
        
        self.editor_btn = QPushButton("Открыть в редакторе")
        self.editor_btn.clicked.connect(self.open_in_external_editor)

        # Временная кнопка для очистки данных
        self.clear_btn = QPushButton("Очистить данные")
        self.clear_btn.clicked.connect(self.clear_data)

        toolbar_layout.addWidget(self.add_folder_btn)
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
        self.folders_tree.clicked.connect(self.on_folder_clicked)
        
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
        
        # Scroll area для блоков папок
        self.scroll_area = QScrollArea()
        self.photos_widget = QWidget()
        self.photos_layout = QVBoxLayout(self.photos_widget)
        self.photos_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.photos_widget)
        self.scroll_area.setWidgetResizable(True)
        
        right_layout.addWidget(self.scroll_area)
        
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
        self.refresh_data()
    
    def connect_signals(self):
        """Подключает сигналы сканирования"""
        self.scan_progress_updated.connect(self.update_scan_progress)
        self.scan_finished.connect(self.on_scan_finished)

    def refresh_data(self):
        """Обновляет данные в интерфейсе"""
        self.load_folders()
        self.load_all_folder_photos()
        
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
            
            # Рекурсивно добавляем все вложенные папки
            added_count = 0
            added_folders = []
            for root, dirs, files in os.walk(folder_path):
                if self.db_manager.add_folder(root):
                    added_count += 1
                    added_folders.append(root)
            
            if added_count > 0:
                self.refresh_data()  # Обновляем данные, включая визуализацию
                
                # Выбираем последнюю добавленную папку и отображаем её фотографии
                if added_folders:
                    latest_folder = added_folders[-1] # Берем последнюю добавленную папку
                    # Находим индекс этой папки в модели
                    for row in range(self.folders_model.rowCount()):
                        index = self.folders_model.index(row, 0)
                        if self.folders_model.data(index, Qt.ItemDataRole.UserRole) == latest_folder:
                            # Выбираем эту папку
                            self.folders_tree.setCurrentIndex(index)
                            # Загружаем фотографии из этой папки
                            folder_id = self.folders_model.data(index, Qt.ItemDataRole.UserRole + 1)
                            self.current_folder = latest_folder
                            self.current_folder_id = folder_id
                            self.update_folder_stats(folder_id, latest_folder)
                            # Прокручиваем к блоку новой папки
                            self.scroll_to_folder_block(folder_id)
                            break
                
                QMessageBox.information(self, "Успех", f"Добавлено {added_count} папок (включая вложенные): {folder_path}")
            else:
                QMessageBox.warning(self, "Ошибка", "Папки уже добавлены или произошла ошибка")

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
                self.refresh_data()
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
        self.update_folder_stats(folder_id, folder_path)
        # Прокручиваем к блоку выбранной папки
        self.scroll_to_folder_block(folder_id)

    def on_folder_clicked(self, index):
        """Обрабатывает одиночный клик на папке - устанавливает акцент на блоке папки"""
        folder_path = self.folders_model.data(index, Qt.ItemDataRole.UserRole)
        folder_id = self.folders_model.data(index, Qt.ItemDataRole.UserRole + 1)
        
        self.current_folder = folder_path
        self.current_folder_id = folder_id
        self.update_folder_stats(folder_id, folder_path)
        # Прокручиваем к блоку выбранной папки
        self.scroll_to_folder_block(folder_id)

    def scroll_to_folder_block(self, folder_id):
        """Прокручивает к блоку указанной папки"""
        if folder_id in self.folder_blocks:
            folder_block = self.folder_blocks[folder_id]
            
            # Получаем позицию блока в виджете
            block_pos = folder_block.pos()
            block_y = block_pos.y()
            
            # Прокручиваем к позиции блока с небольшим отступом сверху
            scroll_value = max(0, block_y - 20)  # 20 пикселей отступа сверху
            self.scroll_area.verticalScrollBar().setValue(scroll_value)

    def load_all_folder_photos(self):
        """Загружает фотографии всех папок в виде блоков"""
        # Очищаем текущие блоки
        for i in reversed(range(self.photos_layout.count())):
            widget = self.photos_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Очищаем словарь блоков
        self.folder_blocks = {}
        
        # Получаем все папки
        folders = self.db_manager.get_all_folders()
        
        row = 0
        for folder_id, folder_path, added_date in folders:
            # Создаем блок для папки
            folder_block = FolderPhotosBlockWidget(folder_path, folder_id, self.db_manager, parent=self)
            
            # Подключаем сигналы
            folder_block.scan_folder.connect(self.on_scan_folder)
            folder_block.delete_folder.connect(self.on_delete_folder)
            folder_block.folder_selected.connect(self.on_folder_block_selected)
            folder_block.photo_double_clicked.connect(self.on_photo_double_clicked)
            
            # Добавляем блок в макет
            self.photos_layout.addWidget(folder_block)
            
            # Сохраняем ссылку на блок
            self.folder_blocks[folder_id] = folder_block
            
            row += 1
            
            # Добавляем зазор 25px между блоками разных папок
            if row < len(folders):
                spacer = QFrame()
                spacer.setFixedHeight(25)
                spacer.setStyleSheet("background-color: transparent;")  # Прозрачный фон
                self.photos_layout.addWidget(spacer)
                row += 1
        
        # Если нет папок, показываем сообщение
        if row == 0:
            no_photos_label = QLabel("Нет папок для отображения")
            no_photos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.photos_layout.addWidget(no_photos_label)

    def on_scan_folder(self, folder_path):
        """Обработка сигнала сканирования папки"""
        # Находим папку в модели по пути
        for row in range(self.folders_model.rowCount()):
            index = self.folders_model.index(row, 0)
            if self.folders_model.data(index, Qt.ItemDataRole.UserRole) == folder_path:
                # Устанавливаем как текущую папку и запускаем сканирование
                folder_id = self.folders_model.data(index, Qt.ItemDataRole.UserRole + 1)
                self.current_folder = folder_path
                self.current_folder_id = folder_id
                self.start_scanning(selected_folder=True)
                break

    def on_delete_folder(self, folder_path):
        """Обработка сигнала удаления папки"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить папку '{folder_path}' из обработки?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.db_manager.remove_folder(folder_path):
                self.refresh_data()
                self.folder_stats_label.setText("Выберите папку для просмотра статистики")
                QMessageBox.information(self, "Успех", "Папка удалена из обработки")

    def on_folder_block_selected(self, folder_path):
        """Обработка выбора блока папки"""
        # Выбираем папку в левом списке
        for row in range(self.folders_model.rowCount()):
            index = self.folders_model.index(row, 0)
            if self.folders_model.data(index, Qt.ItemDataRole.UserRole) == folder_path:
                self.folders_tree.setCurrentIndex(index)
                # Загружаем статистику для выбранной папки
                folder_id = self.folders_model.data(index, Qt.ItemDataRole.UserRole + 1)
                self.current_folder = folder_path
                self.current_folder_id = folder_id
                self.update_folder_stats(folder_id, folder_path)
                break

    def on_photo_double_clicked(self, image_path):
        """Обработка двойного клика по фотографии"""
        self.image_double_clicked.emit(image_path)

    def on_image_double_clicked(self, index):
        """Обрабатывает двойной клик на изображении"""
        # Заглушка для совместимости, используется только в старой реализации
        # В новой реализации используется on_photo_double_clicked
        pass

    def start_scanning(self, selected_folder=False):
        """Начинает сканирование папок на распознавание лиц"""
        if self.scan_manager.is_scanning():
            QMessageBox.information(self, "Информация", "Сканирование уже выполняется")
            return
        
        # Получаем информацию о настройках перед сканированием
        model_name = self.config.get('scan.face_model_name', 'buffalo_l')
        min_confidence = self.config.get('scan.min_face_confidence', 0.7)
        
        # Показываем диалог с информацией о сканировании
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        dialog = QDialog(self)
        dialog.setWindowTitle("Подтверждение сканирования")
        dialog_layout = QVBoxLayout(dialog)
        
        # Информация о параметрах сканирования
        info_label = QLabel(
            f"Будет выполнено сканирование с следующими параметрами:\n\n"
            f"• Модель распознавания: {model_name}\n"
            f"• Минимальное качество обнаружения: {min_confidence}\n\n"
            f"Процесс может занять продолжительное время в зависимости от количества изображений."
        )
        info_label.setWordWrap(True)
        dialog_layout.addWidget(info_label)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        settings_btn = QPushButton("В настройки")
        cancel_btn = QPushButton("Отмена")
        continue_btn = QPushButton("Продолжить")
        
        buttons_layout.addWidget(settings_btn)
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(continue_btn)
        dialog_layout.addLayout(buttons_layout)
        
        # Подключаем действия к кнопкам
        settings_btn.clicked.connect(lambda: self.open_settings())
        cancel_btn.clicked.connect(dialog.reject)
        continue_btn.clicked.connect(dialog.accept)
        
        # Показываем диалог и продолжаем только если нажата "Продолжить"
        if dialog.exec() == QDialog.DialogCode.Accepted:
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
        # QMessageBox.information(self, "Информация", "Сканирование отменено")

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
        
        # Показываем сообщение только при завершении реального сканирования
        # QMessageBox.information(self, "Успех", "Сканирование завершено!")

    def on_scan_error(self, error_message):
        """Обрабатывает ошибки сканирования"""
        self.on_scan_finished()
        QMessageBox.critical(self, "Ошибка сканирования", f"Произошла ошибка: {error_message}")

    def open_in_external_editor(self):
        """Открывает выбранный файл во внешнем редакторе"""
        QMessageBox.warning(self, "Внимание", "Функция временно недоступна в новом интерфейсе папок")
        return
        
        # Получаем путь к внешнему редактору из настроек
        editor_path = self.config.get_external_editor_path()
        
        if not editor_path:
            # Если редактор не задан, предлагаем пользователю его указать
            editor_path, _ = QFileDialog.getOpenFileName(
                self, "Выберите программу для редактирования изображений"
            )
            if editor_path:
                self.config.set_external_editor_path(editor_path)
                QMessageBox.information(self, "Успех", f"Редактор установлен: {editor_path}")
            else:
                QMessageBox.information(self, "Информация", "Открытие во внешнем редакторе отменено")
                return
        
        # Проверяем существование файла редактора
        if not os.path.exists(editor_path):
            QMessageBox.critical(self, "Ошибка", f"Файл внешнего редактора не найден: {editor_path}")
            return
            
        # Открываем файл во внешнем редакторе
        try:
            import subprocess
            subprocess.Popen([editor_path, image_path])
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл во внешнем редакторе: {e}")

    # Метод set_external_editor больше не используется в новом интерфейсе папок

    def rename_image(self, index):
        """Переименовывает изображение"""
        QMessageBox.warning(self, "Внимание", "Функция временно недоступна в новом интерфейсе папок")
        return

    def open_image_in_editor(self, index):
        """Открывает изображение во внешнем редакторе"""
        QMessageBox.warning(self, "Внимание", "Функция временно недоступна в новом интерфейсе папок")
        return

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

    def open_settings(self):
        """Открывает диалог настроек"""
        # Импортируем здесь, чтобы избежать циклических импортов
        from src.photoface.ui.settings_dialog import SettingsDialog
        settings_dialog = SettingsDialog(self.config)
        settings_dialog.exec()
        # После закрытия настроек обновляем конфигурацию в scan_manager
        self.scan_manager.update_config(self.config)