from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QWidget, QLabel, QLineEdit, QPushButton, QFileDialog,
                             QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
                             QFormLayout, QDialogButtonBox, QMessageBox)
from PyQt6.QtCore import Qt
from src.photoface.core.config import Config

class SettingsDialog(QDialog):
    """Диалог настроек приложения"""
    
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setFixedSize(600, 500)
        self.init_ui()
        self.load_settings()
        
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