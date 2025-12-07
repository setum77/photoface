import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QLineEdit, QDialog, QDialogButtonBox, QMessageBox, QMenu,
    QListWidget, QListWidgetItem, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QTimer, QPoint, QSize
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QFont, QMouseEvent, QKeyEvent, QAction, QCursor,
    QPolygon, QImage
)
from PIL import Image
import traceback

logger = logging.getLogger(__name__)


class FaceEditDialog(QDialog):
    """Диалог для редактирования имени лица с автодополнением"""
    
    def __init__(self, current_name="", db_manager=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.persons = []  # Список всех персон для фильтрации
        self.setWindowTitle("Изменить имя лица")
        self.setModal(True)
        self.setFixedSize(300, 220)
        self.init_ui(current_name)
        
    def init_ui(self, current_name):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Введите имя персоны или выберите из списка:"))
        
        self.name_edit = QLineEdit()
        self.name_edit.setText(current_name or "")
        self.name_edit.selectAll()
        self.name_edit.textChanged.connect(self.filter_suggestions)
        self.name_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.name_edit)
        
        # Список предложений
        layout.addWidget(QLabel("Подходящие персоны:"))
        self.suggestions_list = QListWidget()
        self.suggestions_list.setMaximumHeight(100)
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
            if (is_confirmed and query in name.lower() and name.lower() != 'not recognized'):
                
                display_text = f"{name} ({face_count} фото)"
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, person_id)
                self.suggestions_list.addItem(item)
                
    def on_suggestion_double_clicked(self, item):
        """Устанавливает выбранное имя и закрывает диалог"""
        self.name_edit.setText(item.text().split(' (')[0])
        self.accept()
                
    def get_name(self):
        return self.name_edit.text().strip()


class FaceOverlayWidget(QLabel):
    """Виджет для отображения рамки лица и кликабельной области"""
    
    face_clicked = pyqtSignal(int) # face_id
    
    def __init__(self, face_id, bbox, person_name, confidence, parent=None):
        super().__init__(parent)
        self.face_id = face_id
        self.bbox = bbox  # (x, y, width, height) в координатах изображения
        self.person_name = person_name or "Unknown"
        self.confidence = confidence
        self.is_hovered = False
        self.is_selected = False
        self.scale_factor = 1.0
        
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMinimumSize(1, 1)
        
        # Устанавливаем размер и позицию
        x, y, w, h = self.bbox
        self.setGeometry(int(x), int(y), int(w), int(h))
        
        # Устанавливаем стили
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0);")
        
    def set_scale_factor(self, factor):
        """Обновляет масштабный фактор"""
        logger.debug(f"Setting scale factor for face overlay {self.face_id}: {factor}")
        self.scale_factor = factor
        x, y, w, h = self.bbox
        scaled_x = int(x * factor)
        scaled_y = int(y * factor)
        scaled_w = int(w * factor)
        scaled_h = int(h * factor)
        logger.debug(f"Setting geometry for face overlay {self.face_id}: ({scaled_x}, {scaled_y}, {scaled_w}, {scaled_h})")
        self.setGeometry(scaled_x, scaled_y, scaled_w, scaled_h)
        logger.debug(f"Face overlay {self.face_id} scaled: factor={factor}, bbox=({x},{y},{w},{h}) -> ({scaled_x},{scaled_y},{scaled_w},{scaled_h})")
        
    def paintEvent(self, event):
        """Рисует рамку и метку лица"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Определяем цвет рамки
        if self.person_name != "Unknown":
            color = QColor(0, 255, 0)  # Зеленый для известных
        else:
            color = QColor(255, 255, 0)  # Желтый для неизвестных
            
        if self.is_hovered:
            color = color.lighter(150)
        elif self.is_selected:
            color = QColor(0, 0, 255)  # Синий для выделенных
            
        # Рисуем рамку
        pen = QPen(color, max(2, int(3 * self.scale_factor)))
        painter.setPen(pen)
        painter.drawRect(0, 0, self.width(), self.height())
        
        # Рисуем метку только если рамка достаточно большая
        if self.width() > 30 and self.height() > 20:
            self._draw_label(painter)
    
    def _draw_label(self, painter):
        """Рисует метку с именем персоны"""
        text = self.person_name
        if self.confidence < 0.9:
            text += f" ({self.confidence:.2f})"
            
        font = QFont("Arial", max(8, int(10 * self.scale_factor)))
        font.setBold(True)
        painter.setFont(font)
        
        # Измеряем размер текста
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()
        
        # Позиция текста (внутри рамки, сверху)
        text_x = 2
        text_y = text_height + 2
        
        # Рисуем фон для текста
        painter.fillRect(0, 0, text_width + 4, text_height + 4, QColor(0, 0, 0, 180))
        
        # Рисуем текст
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(2, text_height, text)
        
    def mousePressEvent(self, event):
        """Обрабатывает клик по области лица"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.face_clicked.emit(self.face_id)
        super().mousePressEvent(event)
        
    def enterEvent(self, event):
        """Обрабатывает наведение мыши"""
        self.is_hovered = True
        self.update()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Обрабатывает уход мыши"""
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)


class PhotoViewer(QWidget):
    """Просмотрщик фото с оверлеем рамок лиц"""
    
    face_name_changed = pyqtSignal(int, str)  # face_id, new_name
    closed = pyqtSignal()
    
    def __init__(self, db_manager, config=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.config = config
        self.current_image_path = None
        self.original_pixmap = None
        self.scaled_pixmap = None
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 5.0
        self.face_overlays = {}  # face_id -> FaceOverlayWidget
        self.face_data = {}  # face_id -> face_info
        self._display_update_pending = False  # Флаг для предотвращения множественных обновлений
        
        self._init_ui()

    def _schedule_display_update(self, delay=50):
        """Планирует обновление дисплея с предотвращением множественных вызовов"""
        if not self._display_update_pending:
            self._display_update_pending = True
            logger.debug(f"Scheduling display update with delay {delay}ms")
            QTimer.singleShot(delay, self._perform_display_update)

    def _perform_display_update(self):
        """Выполняет обновление дисплея и сбрасывает флаг"""
        self._update_display()
        self._display_update_pending = False
        logger.debug("Display update completed")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Создаем центральный виджет с изображением
        self.central_widget = QWidget()
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        
        # QLabel для отображения изображения
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.image_label.setMinimumSize(1, 1)
        
        # Добавляем виджет с изображением
        self.central_layout.addWidget(self.image_label)
        
        # Создаем overlay для рамок лиц
        self.overlay_widget = QWidget(self.central_widget) # Изменяем родителя на центральный виджет
        self.overlay_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.overlay_widget.setStyleSheet("background-color: rgba(0, 0, 0, 0);")
        self.overlay_widget.hide()
        logger.debug(f"Created overlay widget with parent: {self.overlay_widget.parent()}")
        
        # Добавляем центральный виджет в прокручиваемую область
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.central_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setFrameStyle(QFrame.Shape.NoFrame)
        
        # Подключаем обработчик прокрутки изменение размера области просмотра
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self._on_scroll_changed)
        
        # Также отслеживаем изменения размера viewport для обновления оверлея
        self.scroll_area.viewport().installEventFilter(self)
        
        layout.addWidget(self.scroll_area)
        
        # Устанавливаем фокус для обработки клавиш
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.image_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # Устанавливаем политику размера
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.central_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
    def _pil_to_qimage(self, pil_img):
        """Конвертирует PIL Image в QImage"""
        logger.debug(f"Converting PIL image to QImage, mode: {pil_img.mode}, size: {pil_img.size}")
        if pil_img.mode == "RGB":
            # 3x8 бит на пиксель (24 бита на пиксель)
            logger.debug("Converting RGB image")
            return self._rgb_to_qimage(pil_img)
        elif pil_img.mode == "RGBA":
            # 4x8 бит на пиксель (32 бита на пиксель)
            logger.debug("Converting RGBA image")
            return self._rgba_to_qimage(pil_img)
        else:
            # Конвертируем в RGB если не поддерживаемый режим
            logger.debug(f"Converting {pil_img.mode} image to RGB")
            rgb_img = pil_img.convert("RGB")
            return self._rgb_to_qimage(rgb_img)
    
    def _rgb_to_qimage(self, pil_img):
        """Конвертирует RGB PIL Image в QImage"""
        logger.debug(f"Converting RGB PIL image to QImage, size: {pil_img.size}")
        # Преобразуем PIL изображение в байтовый массив
        data = pil_img.tobytes("raw", "RGB")
        logger.debug(f"Converted PIL image to bytes, length: {len(data)}")
        # Создаем QImage
        qimage = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format.Format_RGB888)
        logger.debug(f"Created QImage with size: {qimage.size()}, format: {qimage.format()}")
        return qimage
        
    def _rgba_to_qimage(self, pil_img):
        """Конвертирует RGBA PIL Image в QImage"""
        logger.debug(f"Converting RGBA PIL image to QImage, size: {pil_img.size}")
        # Преобразуем PIL изображение в байтовый массив
        data = pil_img.tobytes("raw", "RGBA")
        logger.debug(f"Converted PIL image to bytes, length: {len(data)}")
        # Создаем QImage
        qimage = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format.Format_RGBA8888)
        logger.debug(f"Created QImage with size: {qimage.size()}, format: {qimage.format()}")
        return qimage
        
    def load_image(self, image_path):
        """Загружает изображение и лица"""
        if not os.path.exists(image_path):
            QMessageBox.warning(self, "Ошибка", "Файл не существует")
            return False
            
        # Сначала пробуем резервный вариант - прямая загрузка QPixmap
        logger.debug(f"Attempting to load image directly with QPixmap: {image_path}")
        try:
            pixmap = QPixmap(image_path)
            logger.debug(f"Direct QPixmap loading result: isNull={pixmap.isNull()}")
            
            if not pixmap.isNull():
                logger.debug("Successfully loaded image using direct QPixmap method")
            else:
                logger.warning("Direct QPixmap loading failed, trying PIL method")
                # Если прямая загрузка не удалась, пробуем метод с PIL
                from PIL import Image as PILImage
                logger.debug(f"Attempting to load image with PIL: {image_path}")
                pil_img = PILImage.open(image_path)
                logger.debug(f"Successfully loaded PIL image: size={pil_img.size}, mode={pil_img.mode}")
                
                # Проверяем размер изображения
                width, height = pil_img.size
                logger.debug(f"Image dimensions: {width}x{height}")
                
                # Если изображение слишком большое, логируем это
                if width * height > 1000000:  # 10 миллионов пикселей
                    logger.warning(f"Large image detected: {width}x{height} ({width * height} pixels)")
                
                # Конвертируем PIL изображение в QPixmap
                qimage = self._pil_to_qimage(pil_img)
                logger.debug(f"Converted PIL image to QImage: size={qimage.size()}, format={qimage.format()}")
                
                logger.debug("Attempting to create QPixmap from QImage")
                try:
                    pixmap = QPixmap.fromImage(qimage)
                    logger.debug(f"Created QPixmap: size={pixmap.size()}, isNull={pixmap.isNull()}")
                    
                    # Проверяем, успешно ли создан QPixmap
                    if pixmap.isNull():
                        logger.error("Failed to create QPixmap from QImage - pixmap is null")
                        return False
                except Exception as e:
                    logger.error(f"Exception occurred while creating QPixmap from QImage: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return False
        except Exception as e:
            logger.error(f"Ошибка загрузки изображения: {e}")
            logger.debug(f"Falling back to PIL method: {image_path}")
            # Резервный вариант - метод с PIL
            try:
                from PIL import Image as PILImage
                logger.debug(f"Attempting to load image with PIL: {image_path}")
                pil_img = PILImage.open(image_path)
                logger.debug(f"Successfully loaded PIL image: size={pil_img.size}, mode={pil_img.mode}")
                
                # Проверяем размер изображения
                width, height = pil_img.size
                logger.debug(f"Image dimensions: {width}x{height}")
                
                # Если изображение слишком большое, логируем это
                if width * height > 1000000:  # 10 миллионов пикселей
                    logger.warning(f"Large image detected: {width}x{height} ({width * height} pixels)")
                
                # Конвертируем PIL изображение в QPixmap
                qimage = self._pil_to_qimage(pil_img)
                logger.debug(f"Converted PIL image to QImage: size={qimage.size()}, format={qimage.format()}")
                
                logger.debug("Attempting to create QPixmap from QImage")
                try:
                    pixmap = QPixmap.fromImage(qimage)
                    logger.debug(f"Created QPixmap: size={pixmap.size()}, isNull={pixmap.isNull()}")
                    
                    # Проверяем, успешно ли создан QPixmap
                    if pixmap.isNull():
                        logger.error("Failed to create QPixmap from QImage - pixmap is null")
                        return False
                except Exception as pil_error:
                    logger.error(f"Exception occurred while creating QPixmap from QImage in fallback: {pil_error}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return False
            except Exception as fallback_error:
                logger.error(f"PIL fallback method also failed: {fallback_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return False
        
        if pixmap.isNull():
            logger.error(f"Failed to load image: pixmap is null for {image_path}")
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить изображение")
            return False
            
        self.current_image_path = image_path
        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        
        # Загружаем данные о лицах
        self.load_face_data(image_path)
        
        # Отображаем изображение
        self._update_display()
        
        # Создаем оверлеи для лиц
        self._create_face_overlays()
        
        # Подгоняем изображение под размер окна с задержкой, чтобы избежать конфликта с первоначальной отрисовкой
        logger.debug("Scheduling fit_to_window after image load")
        QTimer.singleShot(150, self.fit_to_window)
        
        return True

    def _update_display(self):
        """Обновляет отображение изображения с учетом масштаба"""
        logger.debug(f"Starting _update_display, original_pixmap isNull: {self.original_pixmap.isNull() if self.original_pixmap else 'None'}, scale_factor: {self.scale_factor}")
        if self.original_pixmap and not self.original_pixmap.isNull():
            # Масштабируем изображение
            scaled_size = self.original_pixmap.size() * self.scale_factor
            logger.debug(f"Scaling pixmap from {self.original_pixmap.size()} to {scaled_size}")
            self.scaled_pixmap = self.original_pixmap.scaled(
                scaled_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            logger.debug(f"Scaled pixmap created: {self.scaled_pixmap.size()}")
            
            # Устанавливаем изображение в label
            self.image_label.setPixmap(self.scaled_pixmap)
            logger.debug("Set scaled pixmap to image_label")
            
            # Обновляем размеры overlay
            logger.debug("Calling _update_overlay_geometry")
            self._update_overlay_geometry()
            
            # Обновляем масштаб оверлеев
            logger.debug("Calling _update_face_overlay_scales")
            self._update_face_overlay_scales()
        else:
            logger.warning(f"_update_display skipped: original_pixmap is {'None' if not self.original_pixmap else 'null'}")

    def _update_overlay_geometry(self):
        """Обновляет геометрию оверлея"""
        logger.debug(f"Starting _update_overlay_geometry, scaled_pixmap isNull: {self.scaled_pixmap.isNull() if self.scaled_pixmap else 'None'}")
        if self.scaled_pixmap and not self.scaled_pixmap.isNull():
            # Устанавливаем размер оверлея равным размеру изображения
            overlay_size = self.scaled_pixmap.size()
            logger.debug(f"Resizing overlay to pixmap size: {overlay_size}")
            self.overlay_widget.resize(overlay_size)
            
            # Вычисляем позицию изображения виджете для центрирования оверлея
            # Получаем размеры области прокрутки
            viewport_size = self.scroll_area.viewport().size()
            image_size = self.scaled_pixmap.size()
            logger.debug(f"Viewport size: {viewport_size}, Scaled image size: {image_size}")
            
            # Вычисляем смещения для центрирования
            x_offset = max(0, (viewport_size.width() - image_size.width()) // 2)
            y_offset = max(0, (viewport_size.height() - image_size.height()) // 2)
            logger.debug(f"Calculated offsets: x={x_offset}, y={y_offset}")
            
            # Позиционируем оверлей с учетом смещения для центрирования
            logger.debug(f"Moving overlay to position: ({x_offset}, {y_offset})")
            self.overlay_widget.move(x_offset, y_offset)
            self.overlay_widget.show()
            logger.debug(f"Overlay geometry updated: size={image_size}, offset=({x_offset}, {y_offset})")
        else:
            logger.debug("Hiding overlay: scaled pixmap is null")
            self.overlay_widget.hide()
            logger.debug("Overlay hidden: no scaled pixmap")

        # Обновляем масштаб оверлеев после обновления геометрии
        logger.debug("Calling _update_face_overlay_scales from _update_overlay_geometry")
        self._update_face_overlay_scales()

    def _update_face_overlay_scales(self):
        """Обновляет масштаб всех оверлеев лиц"""
        logger.debug(f"Updating scales for {len(self.face_overlays)} face overlays, scale_factor={self.scale_factor}")
        for face_id, overlay in self.face_overlays.items():
            logger.debug(f"Setting scale for face overlay {face_id}")
            overlay.set_scale_factor(self.scale_factor)
            logger.debug(f"Scale set for face overlay {face_id}")

    def load_face_data(self, image_path):
        """Загружает лица из БД"""
        logger.debug(f"Starting to load face data for image: {image_path}")
        self.face_data.clear()
        try:
            # Используем существующий метод из DatabaseManager
            logger.debug("Calling db_manager.get_image_faces()")
            faces_data = self.db_manager.get_image_faces(image_path)
            logger.debug(f"Loaded {len(faces_data)} faces for image {image_path}")

            for face_id, x1, y1, x2, y2, conf, name, person_id, is_person_status in faces_data:
                logger.debug(f"Processing face {face_id}: x1={x1}, y1={y1}, x2={x2}, y2={y2}, conf={conf}, name={name}, person_id={person_id}, is_person_status={is_person_status}")
                # Вычисляем bbox как (x, y, width, height)
                x = x1
                y = y1
                width = x2 - x1
                height = y2 - y1

                self.face_data[face_id] = {
                    'bbox': (x, y, width, height),
                    'person_name': name,
                    'confidence': conf,
                    'person_id': person_id,
                    'is_person': is_person_status
                }
                logger.debug(f"Face {face_id}: bbox=({x},{y},{width},{height}), name={name}, conf={conf}")

            logger.debug(f"Completed loading face data, total faces in face_data: {len(self.face_data)}")
        except Exception as e:
            logger.error(f"Error loading face data for {image_path}: {e}")
            traceback.print_exc()

    def _create_face_overlays(self):
        """Создает оверлеи для отображения лиц"""
        logger.debug(f"Starting to create face overlays, overlay_widget parent: {self.overlay_widget.parent()}")

        # Удаляем существующие оверлеи
        logger.debug(f"Removing {len(self.face_overlays)} existing face overlays")
        for face_id, overlay in list(self.face_overlays.items()):
            logger.debug(f"Deleting overlay for face {face_id}")
            overlay.deleteLater()
        self.face_overlays.clear()

        # Создаем новые оверлеи для каждого лица
        logger.debug(f"Creating {len(self.face_data)} face overlays")
        for face_id, face_info in self.face_data.items():
            bbox = face_info['bbox']
            person_name = face_info['person_name']
            confidence = face_info['confidence']
            logger.debug(f"Creating overlay for face {face_id}: bbox={bbox}, name={person_name}, confidence={confidence}")

            overlay = FaceOverlayWidget(
                face_id, bbox, person_name, confidence, self.overlay_widget
            )
            logger.debug(f"Created FaceOverlayWidget for face {face_id}")
            overlay.face_clicked.connect(self.edit_face_name)
            self.face_overlays[face_id] = overlay
            logger.debug(f"Added overlay to face_overlays for face {face_id}")

        # Обновляем масштаб оверлеев
        logger.debug("Calling _update_face_overlay_scales")
        self._update_face_overlay_scales()
        logger.debug("Completed creating face overlays")

    def resizeEvent(self, event):
        """Обработка изменения размера виджета"""
        super().resizeEvent(event)
        # При изменении размера окна изображение может изменить размеры при подгонке
        # Обновляем отображение с задержкой, чтобы избежать конфликта с другими обновлениями
        self._schedule_display_update(50)

    def wheelEvent(self, event):
        """Zoom колесиком"""
        # Определяем направление колеса
        delta = event.angleDelta().y()
        if delta > 0:
            # Увеличение
            factor = 1.2
        else:
            # Уменьшение
            factor = 0.8
            
        # Вычисляем новый масштаб
        new_scale = self.scale_factor * factor
        
        # Проверяем ограничения
        if self.min_scale <= new_scale <= self.max_scale:
            self.scale_factor = new_scale
            self._update_display()
            
        event.accept()

    def eventFilter(self, obj, event):
        """Фильтр событий для отслеживания изменений в scroll_area"""
        if obj == self.scroll_area.viewport() and event.type() == event.Type.Resize:
            # Обновляем оверлей при изменении размера области просмотра
            self._schedule_display_update(10)
        return super().eventFilter(obj, event)
        
    def _on_scroll_changed(self, value):
        """Обработчик изменения прокрутки"""
        # При прокрутке оверлей автоматически прокручивается вместе с родительским элементом
        # Нам не нужно обновлять его позицию, так как он дочерний для image_label
        pass  # Убираем обновление оверлея при прокрутке

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.closed.emit()
        elif event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            # Увеличение
            new_scale = min(self.scale_factor * 1.2, self.max_scale)
            if new_scale != self.scale_factor:
                self.scale_factor = new_scale
                self._update_display()
        elif event.key() == Qt.Key.Key_Minus:
            # Уменьшение
            new_scale = max(self.scale_factor * 0.8, self.min_scale)
            if new_scale != self.scale_factor:
                self.scale_factor = new_scale
                self._update_display()
        elif event.key() == Qt.Key.Key_0:
            # Сброс масштаба
            self.scale_factor = 1.0
            self._update_display()
        else:
            super().keyPressEvent(event)

    def edit_face_name(self, face_id):
        """Открывает диалог редактирования имени лица"""
        face_info = self.face_data.get(face_id)
        if not face_info:
            return
            
        dialog = FaceEditDialog(face_info['person_name'], self.db_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.get_name()
            if new_name and new_name != face_info['person_name']:
                if self._update_face_name(face_id, new_name):
                    # Обновляем информацию о лице
                    face_info['person_name'] = new_name
                    # Обновляем is_person статус после изменения
                    face_info['is_person'] = 1 # Так как имя изменено, считаем, что лицо подтверждено
                    self.face_overlays[face_id].person_name = new_name
                    self.face_overlays[face_id].update()
                    self.face_name_changed.emit(face_id, new_name)

    def _update_face_name(self, face_id, new_name):
        """Обновляет имя лица в базе данных с учетом специальных правил"""
        try:
            # Получаем текущую информацию о лице из self.face_data
            face_info = self.face_data.get(face_id)
            if not face_info:
                logger.error(f"Face info not found for face_id {face_id}")
                return False

            current_person_id = face_info['person_id']
            current_person_name = face_info['person_name']

            if not current_person_id or not current_person_name:
                logger.error(f"Invalid current person data for face_id {face_id}: id={current_person_id}, name={current_person_name}")
                return False

            logger.debug(f"Updating face {face_id}: '{current_person_name}' -> '{new_name}'")

            # Проверяем, является ли новое имя существующей персоной
            target_person_id = self.db_manager.get_person_by_name(new_name)
            if target_person_id:
                logger.debug(f"Moving face {face_id} to existing person {target_person_id} ('{new_name}')")
                # Если выбрана уже существующая персона - просто перемещаем лицо
                return self.db_manager.move_face_to_person(face_id, target_person_id)

            # Проверяем, является ли текущая персона "Person_(id)" (т.е. результат кластеризации)
            import re
            person_pattern = r'^Person_\d+$'
            if re.match(person_pattern, current_person_name):
                logger.debug(f"Renaming clustered person {current_person_id} from '{current_person_name}' to '{new_name}'")
                # Обновляем имя текущей персоны
                if self.db_manager.update_person_name(current_person_id, new_name):
                    # Подтверждаем персону
                    self.db_manager.confirm_person(current_person_id)
                    # Устанавливаем is_person = 1 для всех лиц этой персоны
                    person_faces = self.db_manager.get_person_faces(current_person_id)
                    for face_id_in_person, _, _, _, _, _, _, _, _ in person_faces:
                        self.db_manager.set_face_person_status(face_id_in_person, 1)
                    logger.debug(f"Confirmed person {current_person_id} and updated {len(person_faces)} faces")
                    return True
                return False

            # Если текущая персона "not recognized"
            elif current_person_name == 'not recognized':
                logger.debug(f"Creating new person '{new_name}' for face {face_id} from 'not recognized'")
                # Создаем новую персону
                new_person_id = self.db_manager.create_person(new_name)
                if new_person_id:
                    # Перемещаем лицо в новую персону
                    if self.db_manager.move_face_to_person(face_id, new_person_id):
                        # Подтверждаем персону
                        self.db_manager.confirm_person(new_person_id)
                        # Устанавливаем is_person = 1 для этого лица
                        self.db_manager.set_face_person_status(face_id, 1)
                        logger.debug(f"Created and confirmed new person {new_person_id}")
                        return True
                return False

            # В остальных случаях просто обновляем имя персоны
            else:
                logger.debug(f"Updating existing person name from '{current_person_name}' to '{new_name}'")
                person_id = self.db_manager.get_person_by_name(new_name)
                if not person_id:
                    person_id = self.db_manager.create_person(new_name)
                    logger.debug(f"Created new person {person_id} for '{new_name}'")
                return person_id and self.db_manager.move_face_to_person(face_id, person_id)

        except Exception as e:
            logger.error(f"Error updating face name for face_id {face_id}: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка обновления: {e}")
            return False

    def scale_image(self, factor):
        """Масштабирует изображение"""
        new_scale = self.scale_factor * factor
        if self.min_scale <= new_scale <= self.max_scale:
            self.scale_factor = new_scale
            self._update_display()
        
    def fit_to_window(self):
        """Подгоняет изображение под размер окна"""
        if self.original_pixmap:
            # Получаем размер области просмотра
            available_size = self.scroll_area.viewport().size()
            
            # Учитываем отступы
            margin = 20
            available_size.setWidth(available_size.width() - margin)
            available_size.setHeight(available_size.height() - margin)
            
            # Вычисляем масштаб для вмещения изображения
            pixmap_size = self.original_pixmap.size()
            width_ratio = available_size.width() / pixmap_size.width()
            height_ratio = available_size.height() / pixmap_size.height()
            
            new_scale = min(width_ratio, height_ratio)
            
            # Устанавливаем масштаб
            self.scale_factor = max(self.min_scale, min(new_scale, self.max_scale))
            self._update_display()


class PhotoViewerWindow(QWidget):
    """Главное окно просмотра"""
    
    closed = pyqtSignal()
    
    def __init__(self, db_manager, config=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.config = config
        self.is_fullscreen = False
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.viewer = PhotoViewer(self.db_manager, self.config, self)
        self.viewer.closed.connect(self.close)
        layout.addWidget(self.viewer)
        
        # Панель управления
        self._create_control_panel()
        
        self.setWindowTitle("Photo Viewer")
        self.resize(1200, 800)
        
    def _create_control_panel(self):
        self.control_panel = QWidget()
        self.control_panel.setFixedHeight(45)
        layout = QHBoxLayout(self.control_panel)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.control_panel.setStyleSheet("""
            QWidget { background: rgba(0,0,0,0.7); border-radius: 8px; color: white; }
            QPushButton { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); 
                          border-radius: 4px; padding: 5px; min-width: 30px; color: white; font-weight: bold; }
            QPushButton:hover { background: rgba(255,255,255,0.4); }
        """)
        
        # Add filename label
        self.filename_label = QLabel("")
        self.filename_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(self.filename_label)
        
        btns = [
            ("+", self.scale_image, (1.2,), "Zoom In"),
            ("-", self.scale_image, (0.8,), "Zoom Out"),
            ("Fit", self.fit_to_window, (), "Fit to Window"),
            ("FS", self.toggle_fullscreen, (), "Fullscreen (F)"),
            ("F2", self.rename_current_file, (), "Rename File"),
            ("E", self.open_in_external_editor, (), "Open in External Editor"),
            ("✕", self.close, (), "Close (Esc)"),
        ]
        
        for text, func, args, tip in btns:
            btn = QPushButton(text)
            btn.setToolTip(tip)
            if args:
                btn.clicked.connect(lambda _, f=func, a=args: f(*a))
            else:
                btn.clicked.connect(func)
            layout.addWidget(btn)
        
        layout.addStretch()
        self.control_panel.setParent(self)
        
    def show_image(self, image_path):
        if self.viewer.load_image(image_path):
            self.show()
            self.activateWindow()
            self.raise_()
            # Update filename label
            self.filename_label.setText(os.path.basename(image_path))
            return True
        return False
        
        
    def scale_image(self, factor):
        """Масштабирует изображение"""
        self.viewer.scale_image(factor)
        
    def fit_to_window(self):
        """Подгоняет изображение под размер окна"""
        self.viewer.fit_to_window()
        
    def rename_current_file(self):
        """Переименовывает текущий файл"""
        if not self.viewer.current_image_path:
            QMessageBox.warning(self, "Ошибка", "Нет загруженного изображения")
            return

        import os
        from PyQt6.QtWidgets import QInputDialog

        image_path = self.viewer.current_image_path
        directory = os.path.dirname(image_path)
        old_filename = os.path.basename(image_path)
        name, ext = os.path.splitext(old_filename)

        new_name, ok = QInputDialog.getText(
            self,
            "Переименовать файл",
            "Введите новое имя файла:",
            text=name
        )

        if ok and new_name.strip():
            new_filename = new_name.strip() + ext
            new_path = os.path.join(directory, new_filename)

            # Проверяем, существует ли уже файл с таким именем
            if os.path.exists(new_path):
                QMessageBox.warning(self, "Ошибка", f"Файл {new_filename} уже существует")
                return

            try:
                os.rename(image_path, new_path)

                # Обновляем путь к файлу в базе данных
                self.db_manager.update_image_path(image_path, new_path)

                # Обновляем путь в viewer
                self.viewer.current_image_path = new_path

                # Обновляем имя файла в интерфейсе
                self.filename_label.setText(os.path.basename(new_path))

            except OSError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать файл: {e}")

    def open_in_external_editor(self):
        """Открывает текущий файл во внешнем редакторе"""
        if not self.viewer.current_image_path:
            QMessageBox.warning(self, "Ошибка", "Нет загруженного изображения")
            return

        image_path = self.viewer.current_image_path

        # Получаем путь к внешнему редактору из настроек
        editor_path = self.config.get_external_editor_path()

        if not editor_path:
            # Если редактор не задан, предлагаем пользователю его указать
            from PyQt6.QtWidgets import QFileDialog
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Переместить панель в угол
        self.control_panel.move(self.width() - self.control_panel.width() - 20, 20)
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape:
            if self.is_fullscreen:
                self.toggle_fullscreen()
            else:
                self.close()
        elif event.key() == Qt.Key.Key_F2:
            self.rename_current_file()
        elif event.key() == Qt.Key.Key_E:
            self.open_in_external_editor()
        super().keyPressEvent(event)
                
    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.showFullScreen()
            self.setCursor(Qt.CursorShape.BlankCursor)
        else:
            self.showNormal()
            self.setCursor(Qt.CursorShape.ArrowCursor)
            
    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
