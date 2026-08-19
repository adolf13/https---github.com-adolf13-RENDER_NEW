""" Модуль для создания рисунка L03"""
import configparser
import os
from .method_ezdxf import create_document, get_modelspace, draw_line, draw_rec_line, save_document, move_all_x
from size import size


def make(model, width, height, inout, output_path):
    """
    Создает DXF файл для рисунка L01.

    Args:
        width (int): Ширина панели.
        height (int): Высота панели.
        output_path (str): Путь для сохранения DXF файла.
    """
    tools = ['1003']
    
    
    width_panel,height_panel=size(model, width,height, inout)

    # 1. Создаем новый DXF документ
    doc = create_document()
    msp = get_modelspace(doc)

    # 2. Рисуем прямоугольник (контур панели)
    x0, y0 = 0, 0
    x1, y1 = width_panel, height_panel
    draw_rec_line(msp, x0, y0, x1, y1, layer="contour")
    
    
    # Верт линия. 
    x0=260 if inout=='out' else width_panel-228
    draw_line(msp, x0, 0, x0, height_panel, layer="1003")
    
    # вторая верт линия:
    x0=260+381 if inout=='out' else width_panel-228-349
    draw_line(msp, x0, 0, x0, height_panel, layer="1003")
    
    
    
    
    
    
    
    
    
    # Верх гориз линия. На одном уровне с ручкой
    # 1. Читаем конфиг, чтобы найти y_cent ручки
    parser = configparser.ConfigParser()
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'CONFIG'))
    config_path = os.path.join(config_dir, f"{model}.ini")

    y_handle = height_panel / 2 # Значение по умолчанию, если конфиг не найден

    if os.path.exists(config_path):
        parser.read(config_path)
        lock_section = f'lock_{inout}'
        if parser.has_section(lock_section) and parser.has_option(lock_section, 'y_cent'):
            y_handle = parser.getfloat(lock_section, 'y_cent')
        else:
            print(f"⚠️ y_cent не найден в секции [{lock_section}] файла {config_path}")
    else:
        print(f"⚠️ Файл конфигурации не найден: {config_path}")

    # 2. Рисуем горизонтальную линию на уровне ручки
    
    x_start_h = x0
    x_end_h = width_panel if inout=='out' else 0
    draw_line(msp, x_start_h, y_handle, x_end_h, y_handle, layer="1003")
    
    # 2. Рисуем горизонтальную линию под  ручкой
    draw_line(msp, x_start_h, y_handle-308, x_end_h, y_handle-308, layer="1003")
    
    
    # Сдвигаем чертеж так, чтобы его центр был в 0 по оси X
    move_all_x(msp, -width_panel / 2)
    
    
    save_document(doc, output_path)
