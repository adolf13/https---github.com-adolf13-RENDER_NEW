#!/usr/bin/env python3
"""
Скрипт для запуска сервера рендеринга RENDER_NEW.

Этот файл является основной точкой входа для запуска HTTP-сервера.
Он импортирует и настраивает приложение из модуля StartRender.

Пример запуска:
  python run.py

Запуск на другом порту:
  python run.py --port 8000
"""
import sys
from pathlib import Path

# Добавляем корень проекта в PATH, чтобы обеспечить корректность импортов
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from StartRender import create_app, _parse_server_args

if __name__ == "__main__":
    # Парсинг аргументов командной строки для хоста и порта
    server_args = _parse_server_args()
    
    print(f"\n{'='*50}")
    print(f"🚀 RENDER_NEW Server Starting...")
    print(f"   Listening on: http://{server_args.host}:{server_args.port}")
    print(f"{'='*50}\n")
    
    # Создание и запуск Flask-приложения
    create_app().run(
        host=server_args.host,
        port=server_args.port,
        debug=False,
        threaded=True,
    )
