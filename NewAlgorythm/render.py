"""
Рендеринг 3D моделей через Blender (Ubuntu Server)
"""
import os
import shutil
import subprocess
import sys
from typing import Optional, Tuple


def find_blender() -> Optional[str]:
    """Ищет Blender в переменной окружения, PATH и стандартных каталогах."""
    # Поиск в переменной окружения BLENDER_PATH
    blender_path = os.environ.get('BLENDER_PATH')
    if blender_path and os.path.exists(blender_path):
        return blender_path

    blender_in_path = shutil.which("blender")
    if blender_in_path:
        return blender_in_path

    if sys.platform.startswith('linux'):
        # Проверяем стандартные пути
        possible_paths = [
            "/snap/bin/blender",
            # Другие возможные пути для Linux
        ]
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                print(f"✅ Blender найден по пути: {path}")
                return path

    elif sys.platform == 'win32':
        # Проверяем стандартные пути для Windows
        possible_paths = [
            r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                print(f"✅ Blender найден по пути: {path}")
                return path

    print("❌ Blender не найден!")
    if sys.platform.startswith('linux'):
        print("   Проверьте установку: sudo snap install blender --classic")
    else:
        print("   Укажите путь к blender.exe в переменной окружения BLENDER_PATH.")
    return None


def render_with_blender(obj_path: str, output_png: str) -> bool:
    """
    Рендерит OBJ файл через Blender

    Args:
        obj_path: Путь к OBJ файлу
        output_png: Путь для сохранения PNG

    Returns:
        True если рендеринг успешен, иначе False
    """
    # Ищем Blender
    blender_exe = find_blender()
    if blender_exe is None:
        print("⚠️ Blender не найден! Пропускаем рендеринг.")
        return False

    # Путь к скрипту рендеринга
    blender_script = os.path.join(os.path.dirname(__file__), "blender_render.py")
    if not os.path.exists(blender_script):
        print(f"⚠️ Скрипт рендеринга не найден: {blender_script}")
        return False

    # Создаем папку для результата
    os.makedirs(os.path.dirname(output_png) or '.', exist_ok=True)

    print(f"🎨 Рендеринг: {os.path.basename(obj_path)} → {os.path.basename(output_png)}")

    try:
        # Используем полный путь к Blender
        result = subprocess.run([
            blender_exe,
            "--background",
            "--python", blender_script,
            "--",
            os.path.abspath(obj_path),
            os.path.abspath(output_png)
        ],
            cwd=os.path.dirname(os.path.abspath(obj_path)),
            capture_output=True,
            text=True,  # Декодировать stdout/stderr как текст
            encoding='utf-8',  # Явно указываем кодировку UTF-8
            timeout=600)

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        if result.returncode == 0:
            print(f"✅ Рендеринг завершен: {output_png}")
            return True
        else:
            print(f"❌ Ошибка рендеринга (код {result.returncode})")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Рендеринг прерван по таймауту (10 минут)")
        return False
    except FileNotFoundError as e:
        print(f"❌ Blender не найден: {blender_exe}")
        print(f"   Ошибка: {e}")
        return False # Эта ошибка теперь менее вероятна, но оставим для надежности
    except Exception as e:
        print(f"❌ Ошибка при рендеринге: {e}")
        return False


def render_both_sides(output_path: str) -> Tuple[bool, bool]:
    """
    Рендерит обе стороны двери (внешнюю и внутреннюю)

    Args:
        output_path: Базовый путь к OBJ файлам (без _out/_in)

    Returns:
        (внешняя_успешно, внутренняя_успешно)
    """
    out_obj = f"{output_path}_out.obj"
    in_obj = f"{output_path}_in.obj"
    out_png = f"{output_path}_out.png"
    in_png = f"{output_path}_in.png"

    success_out = False
    success_in = False

    # Проверяем наличие Blender
    blender_exe = find_blender()
    if blender_exe is None:
        print("⚠️ Blender не найден! Рендеринг пропущен.")
        print("📌 Установите Blender:")
        print("   sudo snap install blender --classic")
        return False, False

    # Рендерим внешнюю сторону
    if os.path.exists(out_obj):
        print(f"\n📸 Рендеринг внешней стороны...")
        success_out = render_with_blender(out_obj, out_png)
    else:
        print(f"⚠️ Файл не найден: {out_obj}")

    # Рендерим внутреннюю сторону
    if os.path.exists(in_obj):
        print(f"\n📸 Рендеринг внутренней стороны...")
        success_in = render_with_blender(in_obj, in_png)
    else:
        print(f"⚠️ Файл не найден: {in_obj}")

    return success_out, success_in


# Для тестирования модуля
if __name__ == "__main__":
    print("🔍 Тестирование render.py на Ubuntu Server...")
    blender = find_blender()
    if blender:
        print(f"✅ Blender найден: {blender}")
    else:
        print("❌ Blender НЕ найден")
