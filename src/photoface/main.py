import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.photoface.core.database import DatabaseManager
from src.photoface.ui.main_window import MainWindow

def setup_logging():
    """Настройка логирования"""
    # Кастомный форматер для обработки бинарных данных и кириллических символов
    class BinarySafeFormatter(logging.Formatter):
        def format(self, record):
            # Сохраняем оригинальное сообщение
            original_msg = record.msg
            original_args = record.args
            
            try:
                # Обрабатываем сообщение
                if isinstance(original_msg, bytes):
                    try:
                        # Пробуем декодировать как UTF-8
                        record.msg = original_msg.decode('utf-8', errors='replace')
                    except:
                        # Если не удается, конвертируем в шестнадцатеричное представление
                        record.msg = f"<binary_data: {len(original_msg)} bytes>"
                elif isinstance(original_msg, str):
                    # Для строк проверяем, содержит ли она бинарные данные или непечатаемые символы
                    try:
                        # Проверяем, содержит ли строка управляющие символы или нечитаемые символы
                        record.msg = original_msg.encode('utf-8').decode('utf-8')
                    except UnicodeDecodeError:
                        # Если есть проблемы с кодировкой, используем безопасное представление
                        record.msg = original_msg.encode('utf-8', errors='replace').decode('utf-8')
                
                # Обрабатываем аргументы сообщения
                if original_args:
                    processed_args = []
                    for arg in original_args:
                        if isinstance(arg, bytes):
                            try:
                                processed_args.append(arg.decode('utf-8', errors='replace'))
                            except:
                                processed_args.append(f"<binary_data: {len(arg)} bytes>")
                        elif isinstance(arg, str):
                            try:
                                processed_args.append(arg.encode('utf-8').decode('utf-8'))
                            except UnicodeDecodeError:
                                processed_args.append(arg.encode('utf-8', errors='replace').decode('utf-8'))
                        else:
                            processed_args.append(arg)
                    record.args = tuple(processed_args)
            
            except Exception as e:
                # Если возникла ошибка при обработке, используем безопасное сообщение
                record.msg = f"<log_format_error: {str(original_msg)[:100]}...>"
            
            # Вызываем базовый форматер
            formatted = super().format(record)
            
            # Восстанавливаем оригинальное сообщение и аргументы, чтобы не повлиять на другие обработчики
            record.msg = original_msg
            record.args = original_args
            return formatted
    
    formatter = BinarySafeFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Настройка обработчика файла
    file_handler = logging.FileHandler('photo_face_manager.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Настройка обработчика консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

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