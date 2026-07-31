# dxf_functions/mirror.py
import ezdxf
from ezdxf.math import Matrix44

def mirror_y_axis(file_name, axis='x'):
    '''
    Переворачивает полученный dxf файл.
    :param file_name: имя файла
    :param axis: ось для переворота
    :return:
    '''
    print(f"--- Начало отзеркаливания файла: {file_name} ---")
    try:
        doc = ezdxf.readfile(file_name)
        msp = doc.modelspace()
        for entity in msp:
            if axis=='x':
                entity.scale(-1, 1, 1)
            else:
                entity.scale(1,-1,1)
        
        doc.saveas(file_name)
        print(f"--- Отзеркаливание завершено. Файл перезаписан: {file_name} ---")
    except (IOError, ezdxf.DXFStructureError) as e:
        print(f"⚠️ Ошибка при отзеркаливании файла {file_name}: {e}")
        print("--- Отзеркаливание прервано с ошибкой ---")
