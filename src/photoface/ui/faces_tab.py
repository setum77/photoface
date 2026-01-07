import os
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QListView, QGridLayout, QPushButton, QMessageBox,
                             QMenu, QProgressDialog, QLabel, QLineEdit,
                             QDialog, QDialogButtonBox, QScrollArea,
                             QCheckBox, QFrame, QSizePolicy, QToolButton,
                             QListWidget, QListWidgetItem, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QPoint
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QPixmap, QIcon, QFont, QAction
from src.photoface.core.database import DatabaseManager
from src.photoface.core.face_clusterer import FaceClusterer
from src.photoface.ui.photo_viewer import FaceEditDialog
from src.photoface.utils.helpers import generate_thumbnail, pil_to_pixmap
from src.photoface.utils.face_thumbnail_cache import FaceThumbnailCache

# Настройка логирования
logger = logging.getLogger(__name__)

# Глобальный кэш миниатюр лиц (инициализируется в FacesTab)
face_thumbnail_cache = FaceThumbnailCache(cache_size=1000)

class FaceThumbnailWidget(QFrame):
    """Виджет для отображения миниатюры лица с кнопками действий"""
    
    face_confirmed = pyqtSignal(int) # face_id
    face_rejected = pyqtSignal(int)   # face_id
    face_double_clicked = pyqtSignal(str) # image_path
    
    def __init__(self, face_id, image_path, bbox, confidence, is_person_status=None, parent=None, thumbnail_cache=None, person_name=None, is_confirmed_person=None):
        super().__init__(parent)
        self.face_id = face_id
        self.image_path = image_path
        self.bbox = bbox
        self.confidence = confidence
        self.is_person_status = is_person_status  # 1 - подтверждено, 0 - не подтверждено
        self.person_name = person_name  # имя персоны
        self.is_confirmed_person = is_confirmed_person  # статус подтверждения персоны
        # Используем переданный кэш или глобальный
        self.thumbnail_cache = thumbnail_cache or face_thumbnail_cache
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
        self.thumbnail_label.setMouseTracking(True)
        
        # Загружаем и обрезаем миниатюру лица
        self.load_face_thumbnail()
        
        # Кнопки действий
        buttons_layout = QHBoxLayout()
        
        self.confirm_btn = QToolButton()
        self.confirm_btn.setFixedSize(24, 24)
        
        self.confirm_btn.clicked.connect(lambda: self.face_confirmed.emit(self.face_id))
        
        self.reject_btn = QToolButton()
        self.reject_btn.setText("❌")
        self.reject_btn.setToolTip("Отклонить лицо")
        self.reject_btn.setFixedSize(24, 24)
        self.reject_btn.clicked.connect(lambda: self.face_rejected.emit(self.face_id))
        
        self.update_buttons()
        
        # Добавляем кнопки в зависимости от типа персоны
        if self.person_name != 'not recognized':
            if self.is_confirmed_person == 1:  # Подтвержденная персона - показываем обе кнопки
                buttons_layout.addWidget(self.confirm_btn)
                buttons_layout.addWidget(self.reject_btn)
            elif self.is_confirmed_person == 0:  # Неподтвержденная персона - показываем только reject
                buttons_layout.addWidget(self.reject_btn)
        # Для 'not recognized' не показываем никакие кнопки
        
        buttons_layout.addStretch()
        
        # Информация о confidence
        confidence_label = QLabel(f"{self.confidence:.2f}")
        confidence_label.setStyleSheet("font-size: 10px; color: #666;")
        buttons_layout.addWidget(confidence_label)
        
        layout.addWidget(self.thumbnail_label)
        layout.addLayout(buttons_layout)
        
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 3px; }")
        
        # Устанавливаем политику фокуса и включаем обработку двойного клика для всего виджета
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        
        self.update_buttons()
        
        # Убедимся, что виджет может принимать фокус и обрабатывать события
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
    
    def mouseDoubleClickEvent(self, event):
        """Обработка двойного клика по виджету миниатюры"""
        # Проверяем, был ли клик на thumbnail_label
        pos = event.pos()
        # Преобразуем позицию в координаты thumbnail_label
        local_pos = self.thumbnail_label.mapFromParent(pos)
        if self.thumbnail_label.rect().contains(local_pos):
            self.thumbnail_double_clicked()
        # Не вызываем родительский метод, чтобы избежать конфликта
        # super().mouseDoubleClickEvent(event)

    def update_buttons(self):
        if self.is_person_status == 1:  # Подтверждено
            self.confirm_btn.setText("😊")
            self.confirm_btn.setToolTip("Персона подтверждена")
            self.confirm_btn.setEnabled(False)
            self.confirm_btn.setStyleSheet("QToolButton { background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 4px; }")
        else:  # Не подтверждено (0 или None)
            self.confirm_btn.setText("✓")
            self.confirm_btn.setToolTip("Подтвердить лицо")
            self.confirm_btn.setEnabled(True)
            self.confirm_btn.setStyleSheet("QToolButton { border-radius: 4px; }")
        
    def load_face_thumbnail(self):
        """Загружает миниатюру лица из кэша или создает новую"""
        # Получаем миниатюру из кэша
        pixmap = self.thumbnail_cache.get_thumbnail(self.face_id, self.image_path, self.bbox, (120, 120))
        if pixmap:
            self.thumbnail_label.setPixmap(pixmap)
            
    def get_original_image_size(self):
        """Возвращает размер оригинального изображения"""
        from PIL import Image
        try:
            with Image.open(self.image_path) as img:
                return img.size
        except:
            return None
            
    def thumbnail_double_clicked(self):
        """Обрабатывает двойной клик на миниатюре"""
        self.face_double_clicked.emit(self.image_path)
            
class PersonFaceBlockWidget(QWidget):
    """Виджет блока лица с заголовком и миниатюрами лиц персоны"""
    
    rename_person = pyqtSignal(int) # person_id
    confirm_all_faces = pyqtSignal(int) # person_id
    delete_person = pyqtSignal(int) # person_id
    person_selected = pyqtSignal(int)  # person_id
    image_double_clicked = pyqtSignal(str) # image_path
    face_rejected = pyqtSignal(int)  # face_id - сигнал для обработки отклонения лица
    face_confirmed = pyqtSignal(int)  # face_id - сигнал для обработки подтверждения лица
    
    def __init__(self, person_id, person_name, is_confirmed, faces, parent=None, thumbnail_cache=None):
        super().__init__(parent)
        self.person_id = person_id
        self.person_name = person_name
        self.is_confirmed = is_confirmed
        self.faces = self._process_faces_data(faces)
        self.face_widgets = []
        self.thumbnail_cache = thumbnail_cache  # Кэш миниатюр
        self.init_ui()
             
    def _process_faces_data(self, faces_data):
        """Обработка данных о лицах, извлекая person_is_confirmed и сохраняя только нужные поля"""
        processed_faces = []
        for face_data in faces_data:
            if len(face_data) == 10:  # Если включено поле person_is_confirmed
                (face_id, image_id, image_path, x1, y1, x2, y2, confidence, is_person_status, person_is_confirmed_from_face) = face_data
                processed_faces.append((face_id, image_path, x1, y1, x2, y2, confidence, is_person_status))
            else:  # Если поле person_is_confirmed не включено
                processed_faces.append(face_data)
        return processed_faces
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы для всего виджета
        main_layout.setSpacing(0)  # Убираем промежутки между частями
        
        # Header - содержит имя персоны и управляющие кнопки
        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(80)  # Фиксированная высота 80px
        self.header_widget.setStyleSheet("background-color: rgb(200, 200, 200);") # Серый фон
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)
        
        # Имя персоны
        self.name_label = QLabel(self.person_name)
        font = self.name_label.font()
        font.setBold(True)
        font.setPointSize(22)  # Размер шрифта 22 пункта
        self.name_label.setFont(font)
        
        # Устанавливаем цвет шрифта в зависимости от статуса персоны
        if self.is_confirmed:  # Подтвержденная персона
            self.name_label.setStyleSheet("color: rgb(0, 140, 16);")  # Зеленый цвет
        elif self.person_name == 'not recognized':  # Не распознанная персона
            self.name_label.setStyleSheet("color: rgb(0, 0);")  # Черный цвет
        else:  # Неподтвержденная персона
            self.name_label.setStyleSheet("color: rgb(0, 7, 140);")  # Синий цвет
            
        # Создаем промежуточный виджет для добавления отступа
        name_container = QWidget()
        name_layout = QHBoxLayout(name_container)
        name_layout.setContentsMargins(50, 0, 0, 0)  # Отступ 50px от левого края
        name_layout.addWidget(self.name_label)
        name_layout.addStretch()  # Добавляем растягивающийся элемент для правильного выравнивания
        
        header_layout.addWidget(name_container)
        
        # Создаем контейнер для кнопок, чтобы выровнять их по правому краю
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        # Кнопка "Переименовать"
        rename_btn = QPushButton("Переименовать")
        rename_btn.clicked.connect(lambda: self.rename_person.emit(self.person_id))
        buttons_layout.addWidget(rename_btn)
        
        # Кнопка "Подтвердить все лица" - только для подтвержденных персон
        if self.is_confirmed:
            confirm_all_btn = QPushButton("Подтвердить все лица")
            confirm_all_btn.clicked.connect(lambda: self.confirm_all_faces.emit(self.person_id))
            buttons_layout.addWidget(confirm_all_btn)
        
        # Кнопка "Удалить персону"
        delete_btn = QPushButton("Удалить персону")
        delete_btn.clicked.connect(lambda: self.delete_person.emit(self.person_id))
        buttons_layout.addWidget(delete_btn)
        
        header_layout.addWidget(buttons_container)
        
        main_layout.addWidget(self.header_widget)
        
        # Body - содержит миниатюры лиц
        self.body_widget = QWidget()
        self.body_widget.setStyleSheet("background-color: white;")  # Белый фон
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(5, 5, 5, 5)
        
        # Сетка для миниатюр лиц
        self.faces_layout = QGridLayout()
        self.faces_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Добавляем миниатюры лиц
        row, col = 0, 0
        max_cols = 4
        
        for face_data in self.faces:
            # Извлекаем только нужные поля, игнорируя person_is_confirmed если он присутствует
            if len(face_data) >= 8:
                face_id, image_path, x1, y1, x2, y2, confidence, is_person_status = face_data[:8]
            else:
                # Обработка случая, если данных меньше 8
                continue
            bbox = (x1, y1, x2, y2)
            face_widget = FaceThumbnailWidget(
                face_id, image_path, bbox, confidence, is_person_status,
                thumbnail_cache=self.thumbnail_cache, person_name=self.person_name,
                is_confirmed_person=self.is_confirmed
            )
            
            # Подключаем сигналы
            face_widget.face_confirmed.connect(self.on_face_confirmed)
            face_widget.face_rejected.connect(self.on_face_rejected)
            face_widget.face_double_clicked.connect(self.on_face_double_clicked)
            
            self.faces_layout.addWidget(face_widget, row, col)
            self.face_widgets.append(face_widget)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        body_layout.addLayout(self.faces_layout)
        
        main_layout.addWidget(self.body_widget)
        
        # Устанавливаем политику размера для "резиновости" - body должен растягиваться
        self.header_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.body_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
    def on_face_confirmed(self, face_id):
        """Обработка подтверждения лица"""
        logger.debug(f"Face confirmed - face_id: {face_id}")
        # Отправляем сигнал наверх к FacesTab для обработки через сигнал
        self.face_confirmed.emit(face_id)
    
    def on_face_rejected(self, face_id):
        """Обработка отклонения лица - отправляем сигнал наверх для обработки в FacesTab"""
        logger.debug(f"Face rejected - face_id: {face_id}")
        # Отправляем сигнал наверх к FacesTab для обработки
        self.face_rejected.emit(face_id)
    
    def on_face_double_clicked(self, image_path):
        """Обработка двойного клика по лицу"""
        logger.debug(f"Face double clicked - image_path: {image_path}")
        # Передаем сигнал выше через собственный сигнал
        self.image_double_clicked.emit(image_path)
            
    def mousePressEvent(self, event):
        """Обработка клика по блоку персоны"""
        super().mousePressEvent(event)
        # Вызываем сигнал выбора персоны
        self.person_selected.emit(self.person_id)

class PersonNameDialog(QDialog):
    """Диалог для ввода имени персоны с автодополнением"""
    
    def __init__(self, current_name="", db_manager=None, current_person_id=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_person_id = current_person_id
        self.persons = [] # Список всех персон для фильтрации
        self.target_id = None
        self.setWindowTitle("Переименовать персону")
        self.setModal(True)
        self.init_ui(current_name)
        
    def init_ui(self, current_name):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Введите имя персоны или выберите из списка:"))
        
        self.name_edit = QLineEdit()
        self.name_edit.setText(current_name)
        self.name_edit.selectAll()
        self.name_edit.textChanged.connect(self.filter_suggestions)
        layout.addWidget(self.name_edit)
        
        # Список предложений
        layout.addWidget(QLabel("Подходящие персоны:"))
        self.suggestions_list = QListWidget()
        self.suggestions_list.setMaximumHeight(150)
        self.suggestions_list.itemDoubleClicked.connect(self.on_suggestion_double_clicked)
        layout.addWidget(self.suggestions_list)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Загружаем персон и фильтруем сразу
        if self.db_manager:
            self.persons = self.db_manager.get_person_stats()
            self.filter_suggestions()
    
    def filter_suggestions(self):
        """Фильтрует список по введённому тексту"""
        if not self.persons:
            return
            
        query = self.name_edit.text().lower().strip()
        self.suggestions_list.clear()
        
        for person_id, name, is_confirmed, face_count in self.persons:
            if (person_id != self.current_person_id and
                is_confirmed and
                query in name.lower() and
                name.lower() != 'not recognized'):
                
                # Подсчитываем количество подтвержденных и неподтвержденных лиц для персоны
                person_faces = self.db_manager.get_person_faces(person_id)
                confirmed_faces = sum(1 for face in person_faces if len(face) >= 9 and face[8] == 1)  # is_person_status
                unconfirmed_faces = len(person_faces) - confirmed_faces
                
                if confirmed_faces == face_count and face_count > 0:  # Все лица подтверждены
                    display_text = f"{name} ({face_count} фото)"
                elif unconfirmed_faces > 0:  # Есть неподтвержденные лица
                    display_text = f"{name} ({confirmed_faces}+{unconfirmed_faces}={face_count} фото)"
                else:  # Все лица подтверждены или нет лиц
                    display_text = f"{name} ({face_count} фото)"
                    
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, person_id)
                self.suggestions_list.addItem(item)
    
    def on_suggestion_double_clicked(self, item):
        """Устанавливает выбранное имя и закрывает диалог"""
        self.name_edit.setText(item.text().split(' (')[0])
        self.accept()
    
    def get_name_and_target(self):
        """Возвращает новое имя и target_id (если выбрано из списка)"""
        new_name = self.name_edit.text().strip()
        selected_item = self.suggestions_list.currentItem()
        target_id = selected_item.data(Qt.ItemDataRole.UserRole) if selected_item else None
        return new_name, target_id

class FacesTab(QWidget):
    """Вкладка для работы с лицами и группировки"""
    
    image_double_clicked = pyqtSignal(str)
    needs_refresh = pyqtSignal()
    
    def __init__(self, db_manager: DatabaseManager, config=None):
        super().__init__()
        self.db_manager = db_manager
        self.config = config
        self.face_clusterer = FaceClusterer(db_manager, config=config)
        self.current_person_id = None
        self.person_blocks = {}  # Словарь для хранения блоков персон
        # Инициализируем кэш миниатюр с db_manager
        global face_thumbnail_cache
        face_thumbnail_cache = FaceThumbnailCache(db_manager=db_manager, cache_size=1000)
        self.thumbnail_cache = face_thumbnail_cache
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Поле для порога схожести
        similarity_threshold_label = QLabel("Порог схожести:")
        self.similarity_threshold_edit = QLineEdit()
        self.similarity_threshold_edit.setFixedWidth(60)
        # Устанавливаем начальное значение из настроек
        if self.config:
            threshold = self.config.get('scan.similarity_threshold', 0.6)
            self.similarity_threshold_edit.setText(str(threshold))
        
        # Обработчик изменения значения
        self.similarity_threshold_edit.editingFinished.connect(self.on_similarity_threshold_changed)
        
        self.cluster_btn = QPushButton("Группировать лица")
        self.cluster_btn.clicked.connect(self.cluster_faces)
        
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.refresh_data)
                
        self.delete_empty_persons_btn = QPushButton("Удалить персоны без фото")
        self.delete_empty_persons_btn.clicked.connect(self.delete_empty_persons)
                
        # Убираем stats_label из панели инструментов
        # self.stats_label = QLabel("Обновление...")
        # self.stats_label.setMinimumWidth(200)  # Устанавливаем минимальную ширину для лучшего отображения
                
        toolbar_layout.addWidget(similarity_threshold_label)
        toolbar_layout.addWidget(self.similarity_threshold_edit)
        toolbar_layout.addWidget(self.cluster_btn)
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addWidget(self.delete_empty_persons_btn)
        # toolbar_layout.addWidget(self.stats_label)
        toolbar_layout.addStretch()
                
        layout.addLayout(toolbar_layout)
        
        # Основной разделитель
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # Левая панель - список персон
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(250)  # Устанавливаем фиксированную ширину 250px
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("Персоны:"))
        
        self.persons_list = QListView()
        self.persons_model = QStandardItemModel()
        self.persons_list.setModel(self.persons_model)
        self.persons_list.clicked.connect(self.on_person_selected)
        self.persons_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.persons_list.customContextMenuRequested.connect(self.show_person_context_menu)
        self.persons_list.doubleClicked.connect(self.on_person_double_clicked)
        self.persons_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Разрешаем получение фокуса и клавиатурных событий
        # Обработка нажатия клавиш для списка персон
        self.persons_list.keyPressEvent = self.persons_keyPressEvent
        
        left_layout.addWidget(self.persons_list)
        
        # Добавляем информацию о персонах под списком
        self.persons_stats_label = QLabel()
        self.persons_stats_label.setWordWrap(True)
        self.persons_stats_label.setStyleSheet("font-size: 11px; padding: 5px; background-color: #f0f0f0; border: 1px solid #ccc;")
        left_layout.addWidget(self.persons_stats_label)
        
        splitter.addWidget(self.left_panel)
        
        # Правая панель - лица выбранной персоны
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        right_layout.addWidget(QLabel("Лица:"))
        
        # Scroll area для миниатюр лиц
        self.scroll_area = QScrollArea()
        self.faces_widget = QWidget()
        self.faces_layout = QGridLayout(self.faces_widget)
        self.faces_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.faces_widget)
        self.scroll_area.setWidgetResizable(True)
        
        right_layout.addWidget(self.scroll_area)
        
        # Добавляем информацию о лицах под прокруткой
        self.faces_stats_label = QLabel()
        self.faces_stats_label.setWordWrap(True)
        self.faces_stats_label.setStyleSheet("font-size: 11px; padding: 5px; background-color: #f0f0f0; border: 1px solid #ccc;")
        right_layout.addWidget(self.faces_stats_label)
        
        splitter.addWidget(self.right_panel)
        
        # Установка пропорций - левая панель (персоны) фиксированная 250px, остальное - правая панель (лица)
        splitter.setSizes([250, 750]) # Начальные размеры
        layout.addWidget(splitter, 1)
        
        # Загружаем данные
        self.refresh_data()
        
    def refresh_data(self):
        """Обновляет данные в интерфейсе"""
        self.load_persons()
        self.load_all_person_faces()  # Используем новую функцию для загрузки всех лиц
        self.update_stats()
        self.update_persons_stats()
        # Убираем вызов обновления старой статистики
        # self.update_old_stats()
        
    def load_persons(self):
        """Загружает список персоны"""
        self.persons_model.clear()
        persons = self.db_manager.get_person_stats()
        
        # Разделяем подтвержденные и неподтвержденные персоны
        confirmed_persons = []
        unconfirmed_persons = []
        
        for person_id, name, is_confirmed, face_count in persons:
            # Подсчитываем количество подтвержденных и неподтвержденных лиц для персоны
            person_faces = self.db_manager.get_person_faces(person_id)
            confirmed_faces = sum(1 for face in person_faces if len(face) >= 9 and face[8] == 1)  # is_person_status
            unconfirmed_faces = len(person_faces) - confirmed_faces
            
            if is_confirmed:
                confirmed_persons.append((person_id, name, is_confirmed, face_count, confirmed_faces, unconfirmed_faces))
            else:
                unconfirmed_persons.append((person_id, name, is_confirmed, face_count, confirmed_faces, unconfirmed_faces))
        
        # Сортируем подтвержденные персоны по алфавиту
        confirmed_persons.sort(key=lambda x: x[1].lower())  # Сортировка по имени (x[1])
        # Неподтвержденные персоны оставляем в исходном порядке или можно тоже отсортировать по алфавиту
        unconfirmed_persons.sort(key=lambda x: x[1].lower())  # Сортировка по имени (x[1])
        
        # Объединяем списки: сначала подтвержденные (отсортированные), затем неподтвержденные (отсортированные)
        sorted_persons = confirmed_persons + unconfirmed_persons
        
        for person_id, name, is_confirmed, face_count, confirmed_faces, unconfirmed_faces in sorted_persons:
            if confirmed_faces == face_count and face_count > 0:  # Все лица подтверждены
                display_name = f"{name} ({face_count})"
            elif unconfirmed_faces > 0:  # Есть неподтвержденные лица
                display_name = f"{name} ({confirmed_faces}+{unconfirmed_faces}={face_count})"
            else:  # Все лица подтверждены или нет лиц
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
        # Получаем общее количество лиц (все записи в таблице faces)
        total_faces = self.get_total_faces_count()
        # Получаем количество подтвержденных лиц (где is_person = 1)
        confirmed_faces = self.get_confirmed_faces_count()
        # Неопознанные лица - это те, что принадлежат персоне "not recognized"
        unrecognized_id = self.db_manager.get_person_by_name('not recognized')
        unrecognized_faces = 0
        if unrecognized_id:
            unrecognized_faces = len(self.db_manager.get_person_faces(unrecognized_id))
        
        # Обновляем статистику в нижней части правой панели (вместо панели инструментов)
        stats_text = f"Всего найдено лиц: {total_faces} | Подтвержденных: {confirmed_faces} | Не распределенных лиц: {unrecognized_faces} (группа 'not recognized')"
        self.faces_stats_label.setText(stats_text)
        
    def update_persons_stats(self):
        """Обновляет статистику по персонам"""
        persons_stats = self.db_manager.get_person_stats()
        confirmed_persons = sum(1 for _, _, confirmed, _ in persons_stats if confirmed)
        unconfirmed_persons = len(persons_stats) - confirmed_persons
        
        stats_text = f"Персон: {len(persons_stats)}\nПодтвержденных: {confirmed_persons}\nНе подтвержденных: {unconfirmed_persons}"
        self.persons_stats_label.setText(stats_text)
        
    # Удаляем метод update_old_stats, так как он больше не нужен
    # def update_old_stats(self):
    #     """Обновляет старую статистику в панели инструментов (для совместимости)"""
    #     persons_stats = self.db_manager.get_person_stats()
    #     confirmed_persons = sum(1 for _, _, confirmed, _ in persons_stats if confirmed)
    #     total_faces = self.db_manager.get_unrecognized_faces_count()
    #
    #     stats_text = f"Персон: {len(persons_stats)} | Подтвержденных: {confirmed_persons} | Неопознанных лиц: {total_faces}"
    #     self.stats_label.setText(stats_text)
        
    def on_person_selected(self, index):
        """Обрабатывает выбор персоны"""
        person_id = self.persons_model.data(index, Qt.ItemDataRole.UserRole)
        self.current_person_id = person_id
        # Прокручиваем к блоку выбранной персоны
        self.scroll_to_person_block(person_id)
        
    def on_person_double_clicked(self, index):
        """Обрабатывает двойной клик по персоне - вызывает переименование"""
        person_id = self.persons_model.data(index, Qt.ItemDataRole.UserRole)
        person_name = self.persons_model.data(index, Qt.ItemDataRole.UserRole + 1)
        self.rename_person(person_id, person_name)
        
    def persons_keyPressEvent(self, event):
        """Обработка нажатия клавиш для списка персон"""
        if event.key() == Qt.Key.Key_F2:
            # Переименование персоны
            selected_indexes = self.persons_list.selectedIndexes()
            if selected_indexes:
                index = selected_indexes[0]
                person_id = self.persons_model.data(index, Qt.ItemDataRole.UserRole)
                person_name = self.persons_model.data(index, Qt.ItemDataRole.UserRole + 1)
                self.rename_person(person_id, person_name)
        elif event.key() == Qt.Key.Key_Delete:
            # Удаление персоны
            selected_indexes = self.persons_list.selectedIndexes()
            if selected_indexes:
                index = selected_indexes[0]
                person_id = self.persons_model.data(index, Qt.ItemDataRole.UserRole)
                person_name = self.persons_model.data(index, Qt.ItemDataRole.UserRole + 1)
                # Не даем удалить "not recognized"
                if person_name != 'not recognized':
                    self.delete_person(person_id)
        else:
            # Вызываем стандартный обработчик для остальных клавиш
            super(QListView, self.persons_list).keyPressEvent(event)
        
    def load_all_person_faces(self):
        """Загружает лица всех персон в виде блоков"""
        # Очищаем текущие лица
        for i in reversed(range(self.faces_layout.count())):
            widget = self.faces_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Очищаем словарь блоков
        self.person_blocks = {}
        
        # Получаем все персоны
        persons = self.db_manager.get_person_stats()
        
        # Разделяем подтвержденные и неподтвержденные персоны
        confirmed_persons = []
        unconfirmed_persons = []
        
        for person_id, name, is_confirmed, face_count in persons:
            if is_confirmed:
                confirmed_persons.append((person_id, name, is_confirmed, face_count))
            else:
                unconfirmed_persons.append((person_id, name, is_confirmed, face_count))
        
        # Сортируем подтвержденные персоны по алфавиту
        confirmed_persons.sort(key=lambda x: x[1].lower())  # Сортировка по имени (x[1])
        # Неподтвержденные персоны оставляем в исходном порядке или можно тоже отсортировать по алфавиту
        unconfirmed_persons.sort(key=lambda x: x[1].lower())  # Сортировка по имени (x[1])
        
        # Объединяем списки: сначала подтвержденные (отсортированные), затем неподтвержденные (отсортированные)
        sorted_persons = confirmed_persons + unconfirmed_persons
        
        row = 0
        for person_id, name, is_confirmed, face_count in sorted_persons:
            # Получаем лица для персоны
            faces = self.db_manager.get_person_faces(person_id)
            
            # Создаем блок для персоны
            person_block = PersonFaceBlockWidget(person_id, name, is_confirmed, faces, parent=self, thumbnail_cache=self.thumbnail_cache)
            
            # Подключаем сигналы
            person_block.rename_person.connect(self.rename_person)
            person_block.confirm_all_faces.connect(self.confirm_all_faces)
            person_block.delete_person.connect(self.delete_person)
            person_block.person_selected.connect(self.on_person_block_selected)
            person_block.face_rejected.connect(self.on_face_rejected_from_block)
            person_block.face_confirmed.connect(self.on_face_confirmed)
            
            # Подключаем сигнал двойного клика от блока персоны к сигналу вкладки
            person_block.image_double_clicked.connect(self.image_double_clicked)
            
            # Добавляем блок в макет
            self.faces_layout.addWidget(person_block, row, 0)
            
            # Сохраняем ссылку на блок
            self.person_blocks[person_id] = person_block
            
            row += 1
            
            # Добавляем зазор 25px между блоками разных персон
            if row < len(sorted_persons):
                spacer = QFrame()
                spacer.setFixedHeight(25)
                spacer.setStyleSheet("background-color: transparent;")  # Прозрачный фон
                self.faces_layout.addWidget(spacer, row, 0)
                row += 1
        
        # Если нет персон, показываем сообщение
        if row == 0:
            no_faces_label = QLabel("Нет лиц для отображения")
            no_faces_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.faces_layout.addWidget(no_faces_label, 0, 0)
        
        # Обновляем общую статистику по лицам
        self.update_faces_stats(None)
        
    def on_person_block_selected(self, person_id):
        """Обработка выбора блока персоны"""
        # Выбираем персону в левом списке
        for row in range(self.persons_model.rowCount()):
            index = self.persons_model.index(row, 0)
            if self.persons_model.data(index, Qt.ItemDataRole.UserRole) == person_id:
                self.persons_list.setCurrentIndex(index)
                break
        
    def update_faces_stats(self, person_id):
        """Обновляет общую статистику по лицам (не по персоне)"""
        # Обновляем общую статистику вместо статистики по персоне
        total_all_faces = self.get_total_faces_count()
        total_confirmed_faces = self.get_confirmed_faces_count()
        # Неопознанные лица - это те, что принадлежат персоне "not recognized"
        unrecognized_id = self.db_manager.get_person_by_name('not recognized')
        total_unrecognized_faces = 0
        if unrecognized_id:
            total_unrecognized_faces = len(self.db_manager.get_person_faces(unrecognized_id))
        
        stats_text = f"Всего лиц: {total_all_faces} | Подтвержденных: {total_confirmed_faces} | Не распределенных (группа 'not recognized'): {total_unrecognized_faces}"
        self.faces_stats_label.setText(stats_text)
                
    def scroll_to_person_block(self, person_id):
        """Прокручивает к блоку указанной персоны, размещая его вверху области просмотра"""
        if person_id in self.person_blocks:
            person_block = self.person_blocks[person_id]
            
            # Получаем позицию блока в виджете
            block_pos = person_block.pos()
            block_y = block_pos.y()
            
            # Прокручиваем к позиции блока с небольшим отступом сверху, чтобы блок не прилипал к верхней границе
            scroll_value = max(0, block_y - 20)  # 20 пикселей отступа сверху
            self.scroll_area.verticalScrollBar().setValue(scroll_value)
            
    def on_face_confirmed(self, face_id):
        """Обрабатывает подтверждение лица - устанавливает is_person = 1 или открывает диалог редактирования для not recognized"""
        # Получаем информацию о лице и связанной персоне
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, f.image_id, f.person_id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2, f.confidence, f.is_person,
                       p.name as person_name, p.is_confirmed as person_confirmed
                FROM faces f
                JOIN persons p ON f.person_id = p.id
                WHERE f.id = ?
            ''', (face_id,))
            face_info = cursor.fetchone()
        
        if not face_info:
            return
            
        # Получаем имя персоны из результата запроса
        person_name = face_info[9] # индекс поля person_name в SELECT
        
        # Если персона "not recognized", открываем диалог редактирования
        if person_name == 'not recognized':
            dialog = FaceEditDialog("", self.db_manager, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_name = dialog.get_name()
                if new_name:
                    # Создаем новую персону с введенным именем
                    new_person_id = self.db_manager.create_person(new_name)
                    if new_person_id:
                        # Перемещаем лицо в новую персону
                        if self.db_manager.move_face_to_person(face_id, new_person_id):
                            # Подтверждаем персону
                            self.db_manager.confirm_person(new_person_id)
                            # Устанавливаем is_person = 1 для этого лица
                            self.db_manager.set_face_person_status(face_id, 1)
                            self.refresh_data()
        else:
            # Просто устанавливаем is_person = 1 для именованной персоны
            if self.db_manager.set_face_person_status(face_id, 1):
                # Обновляем интерфейс
                self.refresh_data()
                
                # Найти соответствующий виджет и обновить состояние кнопки
                for person_block in self.person_blocks.values():
                    for face_widget in person_block.face_widgets:
                        if face_widget.face_id == face_id:
                            face_widget.is_person_status = 1
                            face_widget.update_buttons()
                            break
                
    def on_face_rejected(self, face_id):
        """Обрабатывает отклонение лица - перемещает лицо в not recognized"""
        # Получаем информацию о лице и связанной персоне
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT f.id, f.image_id, f.person_id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2, f.confidence, f.is_person,
                       p.name as person_name, p.is_confirmed as person_confirmed
                FROM faces f
                JOIN persons p ON f.person_id = p.id
                WHERE f.id = ?
            ''', (face_id,))
            face_info = cursor.fetchone()
        
        if not face_info:
            return
            
        # Получаем имя персоны из результата запроса
        person_name = face_info[9] # индекс поля person_name в SELECT
        
        # Если персона "not recognized", просто отклоняем лицо
        if person_name == 'not recognized':
            # Просто устанавливаем is_person = 0 для лица в not recognized
            if self.db_manager.set_face_person_status(face_id, 0):
                self.refresh_data()
        else:
            # Перемещаем лицо в "not recognized"
            not_recognized_id = self.db_manager.get_person_by_name('not recognized')
            if not_recognized_id:
                if self.db_manager.move_face_to_person(face_id, not_recognized_id):
                    # Устанавливаем is_person = 0 для лица, которое перемещается в "not recognized"
                    self.db_manager.set_face_person_status(face_id, 0)
                    self.refresh_data()
                    self.needs_refresh.emit()
    def on_face_rejected_from_block(self, face_id):
        """Обрабатывает отклонение лица - перемещает лицо в not recognized"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Убрать лицо из персоны?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Перемещаем лицо в "not recognized"
            not_recognized_id = self.db_manager.get_person_by_name('not recognized')
            if not_recognized_id:
                if self.db_manager.move_face_to_person(face_id, not_recognized_id):
                    # Устанавливаем is_person = 0 для лица, которое перемещается в "not recognized"
                    self.db_manager.set_face_person_status(face_id, 0)
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
            
            # Не показываем "Переименовать" и "Подтвердить все лица" для категории "not recognized"
            if person_name != 'not recognized':
                rename_action = QAction("Переименовать   F2", self)
                rename_action.triggered.connect(lambda: self.rename_person(person_id, person_name))
                # Убираем горячую клавишу из контекстного меню, так как она обрабатывается в persons_keyPressEvent
                menu.addAction(rename_action)
                
                if is_confirmed:  # Команда "Подтвердить все лица" теперь только у подтвержденных персон
                    confirm_all_faces_action = QAction("Подтвердить все лица", self)
                    confirm_all_faces_action.triggered.connect(lambda: self.confirm_all_faces(person_id))
                    menu.addAction(confirm_all_faces_action)
            
            delete_action = QAction("Удалить персону", self)
            delete_action.setShortcut("Del")  # Добавляем горячую клавишу для удаления
            delete_action.triggered.connect(lambda: self.delete_person(person_id))
            menu.addAction(delete_action)
            
            menu.exec(self.persons_list.viewport().mapToGlobal(position))
            
    def rename_person(self, person_id, current_name=None):
        """Переименовывает персону или сливает с существующей (предотвращает дубли)"""
        # Если current_name не передан, получаем его из базы данных
        if current_name is None:
            persons = self.db_manager.get_person_stats()
            for p_id, name, _, _ in persons:
                if p_id == person_id:
                    current_name = name
                    break
        
        dialog = PersonNameDialog(current_name, self.db_manager, person_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.get_name_and_target()[0]  # Только имя, игнор target_id
            if not new_name or new_name == current_name:
                return
                
            logger.debug(f"Rename: {current_name} (id={person_id}) -> '{new_name}'")  # Лог для отладки
             
            try:
                # Ищем существующую персону по имени (первый match)
                target_id = self.db_manager.get_person_by_name(new_name)
                
                if target_id and target_id != person_id:
                    # МЕРДЖ: все лица в target + DELETE текущей
                    logger.debug(f"Merge: {person_id} -> {target_id}")
                    if self.db_manager.merge_persons(person_id, target_id):
                        success_msg = f"Лица '{current_name}' **слиты** с '{new_name}' (id={target_id})"
                    else:
                        raise Exception("Ошибка слияния")
                else:
                    # Обычное переименование (если имя новое)
                    logger.debug(f"Rename to new name: '{new_name}' (no target)")
                    if self.db_manager.update_person_name(person_id, new_name):
                        # Автоматически подтверждаем персону при переименовании
                        self.db_manager.confirm_person(person_id)
                        success_msg = f"Персона переименована в **новое** имя '{new_name}' и подтверждена"
                    else:
                        raise Exception("Ошибка переименования")
                
                logger.debug(f"Успех: {success_msg}")
                QMessageBox.information(self, "Успех", success_msg)
                self.refresh_data()
                # Прокручиваем к обновленному блоку персоны
                self.scroll_to_person_block(person_id)
                self.needs_refresh.emit()
                
            except Exception as e:
                error_msg = f"Ошибка операции: {e}"
                logger.error(error_msg)
                QMessageBox.critical(self, "Ошибка", error_msg)
                    
    def confirm_person(self, person_id):
        """Подтверждает персону"""
        if self.db_manager.confirm_person(person_id):
            QMessageBox.information(self, "Успех", "Персона подтверждена")
            self.refresh_data()
            self.needs_refresh.emit()
            
    def confirm_all_faces(self, person_id):
        """Устанавливает is_person = 1 для всех лиц, прикрепленных к персоне"""
        # Получаем все лица для персоны
        person_faces = self.db_manager.get_person_faces(person_id)
        
        # Устанавливаем is_person = 1 для каждого лица
        for face_data in person_faces:
            # Извлекаем только нужные поля, игнорируя person_is_confirmed если он присутствует
            if len(face_data) >= 8:
                face_id = face_data[0]  # первый элемент - это face_id
            else:
                # Обработка случая, если данных меньше 8
                continue
            self.db_manager.set_face_person_status(face_id, 1)
        
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
                for face_data in faces:
                    # Извлекаем только нужные поля, игнорируя person_is_confirmed если он присутствует
                    if len(face_data) >= 8:
                        face_id = face_data[0]
                        # Используем только первые 8 элементов, игнорируя person_is_confirmed если он есть
                        actual_face_data = face_data[:8] if len(face_data) > 8 else face_data
                        if len(actual_face_data) == 8:
                            face_id, _, _, _, _, _, _, _ = actual_face_data
                        else:
                            # Обработка случая, если данных меньше 8
                            continue
                    else:
                        # Обработка случая, если данных меньше 8
                        continue
                    self.db_manager.move_face_to_person(face_id, not_recognized_id)
                
                # Удаляем пустую персону
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM persons WHERE id = ?", (person_id,))
                    conn.commit()
                
                self.refresh_data()
                self.needs_refresh.emit()
                
                # Переносим фокус на персону "not recognized"
                self.select_person_by_name('not recognized')
                
    def select_person_by_name(self, person_name):
        """Выбирает персону по имени"""
        for row in range(self.persons_model.rowCount()):
            index = self.persons_model.index(row, 0)
            if self.persons_model.data(index, Qt.ItemDataRole.UserRole + 1) == person_name:
                self.persons_list.setCurrentIndex(index)
                person_id = self.persons_model.data(index, Qt.ItemDataRole.UserRole)
                self.current_person_id = person_id
                break
                
    def delete_empty_persons(self):
        """Удаляет персоны без фотографий"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить все персоны без фотографий?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Получаем список всех персон
            persons = self.db_manager.get_person_stats()
            empty_persons = [person_id for person_id, name, is_confirmed, face_count in persons if face_count == 0]
            
            if not empty_persons:
                QMessageBox.information(self, "Информация", "Нет персон без фотографий для удаления")
                return
                
            # Удаляем персоны без фотографий
            deleted_count = 0
            for person_id in empty_persons:
                # Перемещаем в not recognized всех, кто может быть у этой персоны
                faces = self.db_manager.get_person_faces(person_id)
                for face_data in faces:
                    # Извлекаем только нужные поля, игнорируя person_is_confirmed если он присутствует
                    if len(face_data) >= 8:
                        face_id = face_data[0]
                        # Используем только первые 8 элементов, игнорируя person_is_confirmed если он есть
                        actual_face_data = face_data[:8] if len(face_data) > 8 else face_data
                        if len(actual_face_data) == 8:
                            face_id, _, _, _, _, _, _ = actual_face_data
                        else:
                            # Обработка случая, если данных меньше 8
                            continue
                    else:
                        # Обработка случая, если данных меньше 8
                        continue
                    not_recognized_id = self.db_manager.get_person_by_name('not recognized')
                    if not_recognized_id:
                        self.db_manager.move_face_to_person(face_id, not_recognized_id)
                
                # Удаляем пустую персону
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM persons WHERE id = ?", (person_id,))
                    conn.commit()
                    deleted_count += 1
            
            QMessageBox.information(self, "Успех", f"Удалено {deleted_count} персон без фотографий")
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

    def on_similarity_threshold_changed(self):
        """Обновляет значение порога схожести в настройках"""
        try:
            new_value = float(self.similarity_threshold_edit.text())
            # Ограничиваем значение в разумных пределах
            if 0.0 <= new_value <= 1.0:
                if self.config:
                    self.config.set('scan.similarity_threshold', new_value)
                    # Обновляем значение в face_clusterer, если он существует
                    if self.face_clusterer:
                        self.face_clusterer.similarity_threshold = new_value
            else:
                # Если значение вне диапазона, восстанавливаем предыдущее
                current_value = self.config.get('scan.similarity_threshold', 0.6) if self.config else 0.6
                self.similarity_threshold_edit.setText(str(current_value))
                QMessageBox.warning(self, "Неверное значение", "Порог схожести должен быть в диапазоне от 0.0 до 1.0")
        except ValueError:
            # Если введено не число, восстанавливаем предыдущее значение
            current_value = self.config.get('scan.similarity_threshold', 0.6) if self.config else 0.6
            self.similarity_threshold_edit.setText(str(current_value))
            QMessageBox.warning(self, "Неверное значение", "Пожалуйста, введите числовое значение для порога схожести")
            
    def get_total_faces_count(self):
        """Возвращает общее количество лиц"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM faces")
            return cursor.fetchone()[0]
            
    def get_confirmed_faces_count(self):
        """Возвращает количество подтвержденных лиц (где is_person = 1)"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM faces WHERE is_person = 1")
            return cursor.fetchone()[0]

