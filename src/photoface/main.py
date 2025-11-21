import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.photoface.core.database import DatabaseManager
from src.photoface.ui.main_window import MainWindow

def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('photo_face_manager.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def main():
    # Настройка логирования
    setup_logging()
    
    # # Добавляем путь к пакету
    # package_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Создание приложения
    app = QApplication(sys.argv)

    # Установка стиля приложения
    app.setStyle('Fusion')
    
    # Инициализация базы данных
    db = DatabaseManager()
    
    # Создание и отображение главного окна
    window = MainWindow(db)
    window.show()
    
    # Запуск основного цикла
    sys.exit(app.exec())

if __name__ == '__main__':
    main()