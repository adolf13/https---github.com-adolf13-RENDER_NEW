"""
Модуль должен создать DXF файл накладки: либо из фала dxf, путем растяжения(старый вариант), либо по алгоритму (новый вариант).

Для начала нужно определить вариант. Составим список накладок для которых есть алгоритм. Если нужное название в нем присутствует-отклываем соотв файл с алгоритмом.

Строка запуска:
model-для определиня размера панели
Pic -рисунок, если в названии присутствует out-наружный, если in-внутренний
side-сторона открывания. Все делаем правыми, в конце если нужно зеркалим.
ширина проема
высота проема 
lock- для определения электронного 
"""
import importlib
import os
import sys
from mirror import mirror_y_axis
from method_ezdxf import move_all_x

# Добавляем родительскую директорию в путь, чтобы можно было импортировать MakePanel как пакет
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)


def MakePanel(model, pic, side, width, height):
    list_ready_pics=['L01', 'L02','L03','L04','L05','L07','L10','L11','L12','C01','C02','C03','NC1', 'NC2','NC3']
    
    # Определяем путь для сохранения DXF файла
    output_path = os.path.join("output", f"{pic}.dxf")
    
    if 'out' in pic or 'OUT' in pic:
        inout = 'out'
    else:
        inout = 'in'
    

    found_alg = False
    for name in list_ready_pics:
        if name in pic: # если рисунок из нового списка, запускаем модуль с его именем
            try:
                # Динамически импортируем модуль (например, MakePanel.L01)
                module = importlib.import_module(f"MakePanel.{name}")
                # Вызываем функцию make с нужными аргументами
                module.make(model, width, height, inout, output_path)
                found_alg = True
                break # Выходим из цикла, так как нашли нужный модуль
            except ImportError as e:
                print(f"⚠️ Не удалось найти модуль {name}.py: {e}")

    if not found_alg:
        print(f"ℹ️  Для рисунка '{pic}' не найден алгоритм, будет запущен старый метод.")
        # здесь будет логика для растягивания старого рисунка
        pass
    
    # После создания получившийся dxf файл нужно отзеркалить, если он левый
    if "L" in side:
        mirror_y_axis(output_path, axis='x')

        
if __name__ == "__main__":
    MakePanel('DELTA PRO PP', 'L02_out', 'L', 950, 2100)