import sys
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def check_and_update_models():
    """Проверяет и обновляет модели InsightFace"""
    try:
        from src.photoface.core.model_manager import ModelManager
        
        print("Проверка моделей InsightFace...")
        model_manager = ModelManager()
        
        # Проверяем, какие модели установлены
        installed_models = model_manager.get_installed_models()
        print(f"Установленные модели: {', '.join(installed_models) or 'Нет'}")
        
        # Проверяем, какие модели доступны для обновления
        updates = model_manager.check_for_updates()
        available_for_download = [model for model, needs_update in updates.items() if needs_update]
        
        if available_for_download:
            print(f"Доступны для загрузки: {', '.join(available_for_download)}")
            
            for model_name in available_for_download:
                size_mb = model_manager.get_model_size(model_name)
                print(f"Загрузка модели {model_name} (~{size_mb} МБ)...")
                
                success = model_manager.download_model(model_name, progress_callback=lambda progress, status: print(f"Прогресс: {progress}% - {status}"))
                if success:
                    print(f"Модель {model_name} успешно загружена")
                else:
                    print(f"Ошибка загрузки модели {model_name}")
        else:
            print("Все модели актуальны")
            
        # Проверим, есть ли модели, которые были загружены, но имеют вложенную структуру
        # для antelopev2
        all_models = model_manager.get_available_models()
        for model_name in all_models:
            if model_name == 'antelopev2':
                is_installed, status_msg = model_manager.get_model_download_status(model_name)
                if is_installed:
                    print(f"Модель {model_name}: {status_msg}")
                    # Проверим модель
                    is_installed, status_msg = model_manager.get_model_download_status(model_name)
                    if is_installed:
                        print(f"Модель {model_name}: {status_msg}")
                    else:
                        print(f"Модель {model_name}: {status_msg}")
            
        return True
        
    except ImportError as e:
        print(f"Ошибка импорта: {e}")
        print("Убедитесь, что все зависимости установлены: pip install -r requirements.txt или pip install photoface")
        return False
    except Exception as e:
        print(f"Ошибка при проверке/обновлении моделей: {e}")
        return False

def main():
    """Основная функция для запуска проверки обновлений моделей"""
    success = check_and_update_models()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()