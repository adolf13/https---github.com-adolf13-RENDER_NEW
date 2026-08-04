""" Модуль для создания рисунка L01"""
from method_ezdxf import create_document, get_modelspace, draw_line, draw_rec_line, save_document
from size import size
import configparser
import os

def make(model, width, height, inout, output_path, furniture=''):
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
    draw_rec_line(msp, x0, y0, x1, y1, layer="contour")
    
    
    
    # Теперь рисунок!
    lines_count=4 if height <= 2150 else 5
    
    # Для начала рассчитаем расстояние между линиями
    size=height_panel/lines_count
    
    # Теперь нужно проверить все линии на пересечения с фурнитурой
    
    parser = configparser.ConfigParser()
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'CONFIG'))
    config_path = os.path.join(config_dir, f"{model}.ini")
    
    if os.path.exists(config_path):
        parser.read(config_path)
        
        
        # Ручка
        lock_section = f'lock_{inout}'
        if parser.has_section(lock_section) and parser.has_option(lock_section, 'y_cent'):
            y_handle = parser.getfloat(lock_section, 'y_cent')
        else:
            y_handle = 809
            print(f"⚠️ y_cent не найден в секции [{lock_section}] файла {config_path}")   
    
        # Доп замок
        lock_section = f'adv_{inout}'
        if parser.has_section(lock_section) and parser.has_option(lock_section, 'from_y_cent'):
            y_adv_lock =y_handle + parser.getfloat(lock_section, 'from_y_cent')
        else:
            y_adv_lock = 809 + 360
            print(f"⚠️ from_y_cent не найден в секции [{lock_section}] файла {config_path}")   
                

        
        
    
    
                        
    if inout=='in':                 
                        
                        
                        
                        
                        
                        
        if parser.has_section(lock_section) and parser.has_option(lock_section, 'y_cent'):  
            
            
            y_adv_lock=
            y_peep=
            y_latch=-1 if inout=='out' else 1
        else:
            print(f"⚠️ y_cent не найден в секции [{lock_section}] файла {config_path}")
    else:
        print(f"⚠️ Файл конфигурации не найден: {config_path}")

    

    
    
    
    
    if 'HOGO' in furniture: # Если замок HOGO
        pass
    else:  # если замок не HOGO!
        
        # для начала нужно рассчитать по средней. Затем, если какая-то линия
        # пересечет замок - оставшиеся линии нужно пересчитать. Для внутреннней проверить задвижку
        start_between=height_panel/lines_count
        
        # Нижняя линия
        draw_line(msp, 0, start_between, width_panel, start_between, layer="1003")
        
        # Верхняя линия. Нужно проверить на пересечение с нижним замком
        

        
        
        
        
        pass
    
    
    
    
    






    
    
    
    
    
    
    

    # 3. Сохраняем документ
    save_document(doc, output_path)
    
    
    
    
    
    
    
    
    
    
    
if __name__ == "__main__":
    make('DELTA PRO PP', 950, 2100, 'in', 'test.dxf')