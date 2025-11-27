from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QWidget, QLabel, QLineEdit, QPushButton, QFileDialog,
                             QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
                             QFormLayout, QDialogButtonBox, QMessageBox, QProgressBar)
from PyQt6.QtCore import Qt
from src.photoface.core.config import Config
from src.photoface.core.model_manager import ModelManager

class SettingsDialog(QDialog):
    """Диалог настроек приложения"""
    
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.model_manager = ModelManager()
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setFixedSize(600, 500)
        self.init_ui()
        self.load_settings()
        
    def check_model_updates(self):
        """Проверяет обновления моделей"""
        try:
            self.model_status_label.setText("Проверка обновлений...")
            self.model_progress.setVisible(True)
            self.model_progress.setValue(0)
            self.model_progress.setFormat("Проверка: %p%")
            
            # Имитация прогресса для визуального отображения
            import time
            for i in range(1, 11):
                time.sleep(0.02)  # Небольшая задержка для визуального эффекта
                self.model_progress.setValue(i * 10)
            
            updates = self.model_manager.check_for_updates()
            installed_models = self.model_manager.get_installed_models()
            
            status_text = f"Установленные модели: {', '.join(installed_models) or 'Нет'}\n"
            
            available_for_download = [model for model, needs_update in updates.items() if needs_update]
            if available_for_download:
                status_text += f"Доступны для загрузки: {', '.join(available_for_download)}"
            else:
                status_text += "Все модели загружены"
                
            self.model_status_label.setText(status_text)
            self.model_progress.setValue(100)
            self.model_progress.setFormat("Готово")
            time.sleep(0.1)  # Небольшая задержка перед скрытием
            self.model_progress.setVisible(False)
            self.model_progress.setValue(0)
            
            QMessageBox.information(self, "Проверка обновлений", status_text)
            
        except Exception as e:
            self.model_status_label.setText(f"Ошибка проверки: {str(e)}")
            self.model_progress.setVisible(False)
            self.model_progress.setValue(0)
            QMessageBox.critical(self, "Ошибка", f"Ошибка при проверке обновлений: {e}")
    
    def download_selected_model(self):
        """Загружает выбранную модель"""
        try:
            # Определяем выбранную модель
            model_map = {
                0: 'buffalo_l',
                1: 'buffalo_s',
                2: 'antelopev2'
            }
            selected_model = model_map.get(self.model_combo.currentIndex(), 'buffalo_l')
            
            # Проверяем статус текущей модели
            is_installed, status_msg = self.model_manager.get_model_download_status(selected_model)
            
            if is_installed:
                reply = QMessageBox.question(
                    self,
                    "Подтверждение",
                    f"Модель {selected_model} уже установлена. Перезагрузить?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
            else:
                # Показываем предупреждение о размере
                size_mb = self.model_manager.get_model_size(selected_model)
                reply = QMessageBox.question(
                    self,
                    "Подтверждение загрузки",
                    f"Загрузить модель {selected_model}? Размер: ~{size_mb} МБ\n\n"
                    f"Статус: {status_msg}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
            
            # Показываем прогресс
            self.model_status_label.setText(f"Загрузка модели {selected_model}...")
            self.model_progress.setVisible(True)
            self.model_progress.setValue(0)  # Установить начальное значение
            self.model_progress.setFormat(f"Загрузка {selected_model}: %p%")
            
            # Функция обратного вызова для обновления прогресса
            def update_progress(progress, status):
                if progress >= 0:
                    self.model_progress.setValue(progress)
                    self.model_status_label.setText(status)
                else:
                    # Ошибка
                    self.model_progress.setValue(0)
                    self.model_status_label.setText(status)
            
            # Загружаем модель с обновлением прогресса
            success = self.model_manager.download_model(selected_model, update_progress)
            
            # В случае успеха обновим информацию о моделях
            if success:
                installed_models = self.model_manager.get_installed_models()
                status_text = f"Установленные модели: {', '.join(installed_models) or 'Нет'}"
                self.model_status_label.setText(status_text)
            
            # Скрываем прогресс-бар после завершения
            self.model_progress.setVisible(False)
            self.model_progress.setValue(0)
            
            if success:
                self.model_status_label.setText(f"Модель {selected_model} успешно загружена")
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Модель {selected_model} успешно загружена и готова к использованию"
                )
            else:
                self.model_status_label.setText(f"Ошибка загрузки модели {selected_model}")
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось загрузить модель {selected_model}"
                )
                
        except Exception as e:
            self.model_status_label.setText(f"Ошибка загрузки: {str(e)}")
            self.model_progress.setVisible(False)
            self.model_progress.setRange(0, 1)
            QMessageBox.critical(self, "Ошибка", f"Ошибка при загрузке модели: {e}")
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Вкладки настроек
        self.tabs = QTabWidget()
        
        # Вкладка общих настроек
        self.general_tab = self.create_general_tab()
        self.tabs.addTab(self.general_tab, "Общие")
        
        # Вкладка сканирования
        self.scan_tab = self.create_scan_tab()
        self.tabs.addTab(self.scan_tab, "Сканирование")
        
        # Вкладка экспорта
        self.export_tab = self.create_export_tab()
        self.tabs.addTab(self.export_tab, "Экспорт")
        
        layout.addWidget(self.tabs)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_settings)
        
        layout.addWidget(buttons)
        
    def create_general_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Настройки редактора
        editor_group = QGroupBox("Внешний редактор изображений")
        editor_layout = QFormLayout(editor_group)
        
        self.editor_path_edit = QLineEdit()
        self.editor_browse_btn = QPushButton("Обзор...")
        self.editor_browse_btn.clicked.connect(self.browse_editor)
        
        editor_path_layout = QHBoxLayout()
        editor_path_layout.addWidget(self.editor_path_edit)
        editor_path_layout.addWidget(self.editor_browse_btn)
        
        editor_layout.addRow("Путь к редактору:", editor_path_layout)
        
        self.open_after_edit_check = QCheckBox("Открывать изображение после редактирования")
        editor_layout.addRow("", self.open_after_edit_check)
        
        layout.addWidget(editor_group)
        
        # Настройки производительности
        perf_group = QGroupBox("Производительность")
        perf_layout = QFormLayout(perf_group)
        
        self.thumbnail_size_spin = QSpinBox()
        self.thumbnail_size_spin.setRange(100, 400)
        self.thumbnail_size_spin.setSuffix(" px")
        perf_layout.addRow("Размер миниатюр:", self.thumbnail_size_spin)
        
        self.max_threads_spin = QSpinBox()
        self.max_threads_spin.setRange(1, 8)
        self.max_threads_spin.setSuffix(" потоков")
        perf_layout.addRow("Максимум потоков:", self.max_threads_spin)
        
        self.cache_thumbnails_check = QCheckBox("Кэшировать миниатюры")
        perf_layout.addRow("", self.cache_thumbnails_check)
        
        layout.addWidget(perf_group)
        layout.addStretch()
        
        return tab
        
    def create_scan_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Настройки распознавания
        recognition_group = QGroupBox("Распознавание лиц")
        recognition_layout = QFormLayout(recognition_group)
        
        self.similarity_threshold_spin = QDoubleSpinBox()
        self.similarity_threshold_spin.setRange(0.1, 0.99)
        self.similarity_threshold_spin.setSingleStep(0.05)
        self.similarity_threshold_spin.setDecimals(2)
        recognition_layout.addRow("Порог схожести:", self.similarity_threshold_spin)
        
        self.min_confidence_spin = QDoubleSpinBox()
        self.min_confidence_spin.setRange(0.1, 0.99)
        self.min_confidence_spin.setSingleStep(0.05)
        self.min_confidence_spin.setDecimals(2)
        recognition_layout.addRow("Минимальное качество:", self.min_confidence_spin)
        
        self.auto_cluster_check = QCheckBox("Автоматическая группировка после сканирования")
        recognition_layout.addRow("", self.auto_cluster_check)
        
        # Выбор модели
        from PyQt6.QtWidgets import QComboBox
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "buffalo_l (сбалансированная модель)",
            "buffalo_s (быстрая модель)",
            "antelopev2 (современная модель)"
        ])
        recognition_layout.addRow("Модель распознавания:", self.model_combo)
        
        # Информация о моделях
        model_info_label = QLabel(
            "buffalo_l: Сбалансированная модель с высокой точностью\n"
            "buffalo_s: Более быстрая, но менее точная модель\n"
            "antelopev2: Современная модель с улучшенной архитектурой"
        )
        model_info_label.setWordWrap(True)
        model_info_label.setStyleSheet("font-size: 9px; color: #66;")
        recognition_layout.addRow("", model_info_label)
        
        # Управление моделями
        model_management_layout = QHBoxLayout()
        
        self.check_updates_btn = QPushButton("Проверить обновления")
        self.check_updates_btn.clicked.connect(self.check_model_updates)
        model_management_layout.addWidget(self.check_updates_btn)
        
        self.download_model_btn = QPushButton("Загрузить модель")
        self.download_model_btn.clicked.connect(self.download_selected_model)
        model_management_layout.addWidget(self.download_model_btn)
        
        recognition_layout.addRow("", model_management_layout)
        
        # Статус загрузки
        self.model_status_label = QLabel("Статус: Готово")
        self.model_status_label.setWordWrap(True)
        recognition_layout.addRow("Статус моделей:", self.model_status_label)
        
        # Прогресс-бар для загрузки
        self.model_progress = QProgressBar()
        self.model_progress.setVisible(False)
        recognition_layout.addRow("Прогресс загрузки:", self.model_progress)
        
        layout.addWidget(recognition_group)
        layout.addStretch()
        
        return tab
        
    def create_export_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Настройки экспорта
        export_group = QGroupBox("Экспорт альбомов")
        export_layout = QFormLayout(export_group)
        
        self.create_info_check = QCheckBox("Создавать информационные файлы")
        export_layout.addRow("", self.create_info_check)
        
        self.preserve_structure_check = QCheckBox("Сохранять структуру папок")
        export_layout.addRow("", self.preserve_structure_check)
        
        layout.addWidget(export_group)
        layout.addStretch()
        
        return tab
        
    def browse_editor(self):
        """Открывает диалог выбора редактора"""
        editor_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите программу для редактирования изображений", 
            self.editor_path_edit.text(),
            "Программы (*.exe);;Все файлы (*.*)"
        )
        if editor_path:
            self.editor_path_edit.setText(editor_path)
            
    def load_settings(self):
        """Загружает настройки в UI"""
        # Общие настройки
        self.editor_path_edit.setText(self.config.get_external_editor_path())
        self.open_after_edit_check.setChecked(self.config.get('editor.open_after_edit', True))
        self.thumbnail_size_spin.setValue(self.config.get('performance.thumbnail_size', 200))
        self.max_threads_spin.setValue(self.config.get('performance.max_threads', 4))
        self.cache_thumbnails_check.setChecked(self.config.get('performance.cache_thumbnails', True))
        
        # Настройки сканирования
        self.similarity_threshold_spin.setValue(self.config.get('scan.similarity_threshold', 0.6))
        self.min_confidence_spin.setValue(self.config.get('scan.min_face_confidence', 0.7))
        self.auto_cluster_check.setChecked(self.config.get('scan.auto_cluster_after_scan', True))
        
        # Загрузка модели
        model_name = self.config.get('scan.face_model_name', 'buffalo_l')
        model_map = {
            'buffalo_l': 0,
            'buffalo_s': 1,
            'antelopev2': 2
        }
        self.model_combo.setCurrentIndex(model_map.get(model_name, 0))
        
        # Настройки экспорта
        self.create_info_check.setChecked(self.config.get('export.create_info_files', True))
        self.preserve_structure_check.setChecked(self.config.get('export.preserve_folder_structure', False))
        
    def apply_settings(self):
        """Применяет настройки"""
        try:
            # Общие настройки
            self.config.set_external_editor_path(self.editor_path_edit.text())
            self.config.set('editor.open_after_edit', self.open_after_edit_check.isChecked())
            self.config.set('performance.thumbnail_size', self.thumbnail_size_spin.value())
            self.config.set('performance.max_threads', self.max_threads_spin.value())
            self.config.set('performance.cache_thumbnails', self.cache_thumbnails_check.isChecked())
            
            # Настройки сканирования
            self.config.set('scan.similarity_threshold', self.similarity_threshold_spin.value())
            self.config.set('scan.min_face_confidence', self.min_confidence_spin.value())
            self.config.set('scan.auto_cluster_after_scan', self.auto_cluster_check.isChecked())
            
            # Сохранение модели
            model_map = {
                0: 'buffalo_l',
                1: 'buffalo_s',
                2: 'antelopev2'
            }
            selected_model = model_map.get(self.model_combo.currentIndex(), 'buffalo_l')
            self.config.set('scan.face_model_name', selected_model)
            
            # Настройки экспорта
            self.config.set('export.create_info_files', self.create_info_check.isChecked())
            self.config.set('export.preserve_folder_structure', self.preserve_structure_check.isChecked())
            
            QMessageBox.information(self, "Успех", "Настройки сохранены")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки: {e}")
            
    def accept(self):
        """Обрабатывает нажатие OK"""
        self.apply_settings()
        super().accept()