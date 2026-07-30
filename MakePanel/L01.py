""" Модуль для создания рисунка L01"""
from method_ezdxf import create_document, get_modelspace, draw_line, draw_rectangle, save_document
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
    # Обычно контур находится в слое "0"

    x0, y0 = 0, 0
    x1, y1 = width_panel, height_panel
    draw_rectangle(msp, x0, y0, x1, y1)

    # 3. Сохраняем документ
    save_document(doc, output_path)
    
    
if __name__ == "__main__":
    make('DELTA PRO PP', 950, 2100, 'in', 'test.dxf')