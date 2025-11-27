import os
from PIL import Image, ImageOps
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap, QImage

def generate_thumbnail(image_path, size=(200, 200)):
    """Генерирует миниатюру изображения"""
    try:
        with Image.open(image_path) as img:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Создаем миниатюру с сохранением пропорций
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Создаем квадратную миниатюру с белым фоном
            thumb = ImageOps.fit(img, size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            return thumb
    except Exception as e:
        print(f"Ошибка создания миниатюры для {image_path}: {e}")
        return None

def pil_to_pixmap(pil_image):
    """Конвертирует PIL Image в QPixmap"""
    if pil_image is None:
        return QPixmap()
    
    # Конвертируем PIL Image в QImage
    if pil_image.mode == "RGB":
        rgb_image = pil_image
    else:
        rgb_image = pil_image.convert("RGB")
    
    data = rgb_image.tobytes("raw", "RGB")
    q_image = QImage(data, rgb_image.size[0], rgb_image.size[1], QImage.Format.Format_RGB888)
    return QPixmap.fromImage(q_image)

def get_image_files(folder_path):
    """Возвращает список файлов изображений в папке и всех подпапках"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    image_files = []
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path):
                _, ext = os.path.splitext(file.lower())
                if ext in image_extensions:
                    image_files.append(file_path)
    
    return sorted(image_files)