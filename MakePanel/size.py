# Модуль возвращает размер накладки
import configparser
import os


def size(model, width_door, height_door, inout):
    
    """
    Возвращает размер накладки (панели), вычитая отступы из размеров двери.

    Отступы берутся из ini-файла модели.

    Args:
        model (str): Название модели, соответствует имени .ini файла (без расширения).
        width_door (float): Ширина двери.
        height_door (float): Высота двери.
        inout (str): Сторона накладки ('in' или 'out').

    Returns:
        tuple[float, float]: Кортеж (width_panel, height_panel).
    """
    parser = configparser.ConfigParser()

    # Путь к папке CONFIG, которая находится на уровень выше текущего модуля
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CONFIG'))
    config_path = os.path.join(config_dir, f"{model}.ini")

    if not os.path.exists(config_path):
        print(f"⚠️ Файл конфигурации не найден: {config_path}")
        return width_door, height_door

    parser.read(config_path)

    section = f'size_{inout}'

    if not parser.has_section(section):
        print(f"⚠️ Секция [{section}] не найдена в файле {config_path}")
        return width_door, height_door

    width_offset = parser.getfloat(section, 'width', fallback=0.0)
    height_offset = parser.getfloat(section, 'height', fallback=0.0)

    width_panel = width_door - width_offset
    height_panel = height_door - height_offset

    return width_panel, height_panel


if __name__ == "__main__":
    w,h=size('DELTA PRO PP', 950, 2100, 'in')
    print(w,h)
    