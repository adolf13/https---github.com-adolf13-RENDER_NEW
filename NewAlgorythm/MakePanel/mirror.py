# dxf_functions/mirror.py
import ezdxf
from ezdxf.math import Matrix44
#from ezdxf.errors import NoEntitiesError

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

def mirror_y_axis(file_name, axis='x'):
    '''
    Переворачивает полученный dxf файл.
    :param file_name: имя файла
    :param axis: ось для переворота
    :return:
    '''
    doc = ezdxf.readfile(file_name)
    msp = doc.modelspace()
    for entity in msp:
        if axis=='x':
            entity.scale(-1, 1, 1)
        else:
            entity.scale(1,-1,1)
            
            
            
    # if axis == 'x':
    #     transform = Matrix44.scale(-1, 1, 1) @ Matrix44.translate(width, 0, 0)
    #     for entity in msp:
    #         entity.transform(transform)
            
    doc.saveas(file_name)



