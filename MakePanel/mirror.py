# dxf_functions/mirror.py
import ezdxf
from ezdxf.math import Matrix44

# --- Старые функции, работающие со словарями ---
# Эти функции, вероятно, больше не используются
def mirror_point(point, axis='x'):
    """Зеркальное отражение точки"""
    x, y = point
    if axis == 'x':
        return (-x, y)
    return (x, y)


def mirror_entity(entity, axis='x'):
    """Зеркальное отражение примитива"""
    mirrored = entity.copy()
    entity_type = entity.get('type')

    if entity_type == 'LINE':
        mirrored['x1'] = mirror_point((entity['x1'], entity['y1']), axis)[0]
        mirrored['y1'] = mirror_point((entity['x1'], entity['y1']), axis)[1]
        mirrored['x2'] = mirror_point((entity['x2'], entity['y2']), axis)[0]
        mirrored['y2'] = mirror_point((entity['x2'], entity['y2']), axis)[1]
    elif entity_type == 'CIRCLE':
        mirrored['x'] = mirror_point((entity['x'], entity['y']), axis)[0]
        mirrored['y'] = mirror_point((entity['x'], entity['y']), axis)[1]
    elif entity_type == 'ARC':
        mirrored['x'] = mirror_point((entity['x'], entity['y']), axis)[0]
        mirrored['y'] = mirror_point((entity['x'], entity['y']), axis)[1]
        # Для дуги нужно отразить углы
        if axis == 'x':
            mirrored['start_angle'] = 180 - entity['end_angle']
            mirrored['end_angle'] = 180 - entity['start_angle']
    elif entity_type == 'LWPOLYLINE':
        mirrored['points'] = [mirror_point(p, axis) for p in entity['points']]

    return mirrored


def mirror_entities(entities, axis='x'):
    """Зеркальное отражение всех примитивов"""
    return [mirror_entity(entity, axis) for entity in entities]


# --- Новая функция для отзеркаливания DXF файла ---

def mirror_dxf_horizontally(filepath: str):
    """
    Отзеркаливает содержимое DXF файла по горизонтали (относительно вертикальной оси).

    Открывает DXF-файл, находит центр его содержимого по оси X, зеркально
    отражает все объекты относительно этой центральной вертикальной линии и
    сохраняет изменения в тот же файл.

    Args:
        filepath (str): Путь к DXF файлу для модификации.
    """
    try:
        doc = ezdxf.readfile(filepath)
        msp = doc.modelspace()
    except IOError:
        print(f"⚠️ Не удалось прочитать файл: {filepath}")
        return
    except ezdxf.DXFStructureError:
        print(f"⚠️ Неверный или поврежденный DXF файл: {filepath}")
        return

    # 1. Находим габариты всего чертежа
    try:
        extents = msp.get_extents()
    except ezdxf.math.BoundingBoxError:
        print(f"ℹ️ Файл '{filepath}' пуст, отзеркаливание не требуется.")
        return  # В файле нет объектов для отзеркаливания

    # 2. Вычисляем центральную ось X
    center_x = (extents.extmin.x + extents.extmax.x) / 2

    # 3. Создаем матрицу трансформации для зеркального отражения
    transform = Matrix44.scale(-1, 1, 1) @ Matrix44.translate(center_x, 0, 0)

    # 4. Применяем трансформацию ко всем объектам
    for entity in msp:
        entity.transform(transform)

    # 5. Сохраняем изменения в тот же файл
    doc.save()
    print(f"✅ Файл отзеркален: {filepath}")