""" Модуль для создания рисунка L01"""
from . import method_ezdxf as dxf
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
    doc = dxf.create_document()
    msp = dxf.get_modelspace(doc)

    # 2. Рисуем прямоугольник (контур панели)
    # Обычно контур находится в слое "0"

    x0, y0 = 0, 0
    x1, y1 = width_panel, height_panel
    dxf.draw_rectangle(msp, x0, y0, x1, y1)

    # 3. Сохраняем документ
    dxf.save_document(doc, output_path)