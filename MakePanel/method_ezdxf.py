# dxf_functions/method_ezdxf.py
import ezdxf
import os
import math


def create_document(version='R2000'):
    """
    Создает новый DXF документ.

    Args:
        version: Версия DXF (по умолчанию 'R2000')

    Returns:
        ezdxf.Drawing: Новый документ
    """
    return ezdxf.new(version)


def get_modelspace(doc):
    """
    Возвращает modelspace из документа.

    Args:
        doc: DXF документ

    Returns:
        Modelspace: Пространство модели
    """
    return doc.modelspace()


def draw_line(msp, x1, y1, x2, y2, color=7):
    """
    Рисует линию в modelspace.

    Args:
        msp: Modelspace
        x1, y1: Начальная точка
        x2, y2: Конечная точка
        color: Цвет (по умолчанию 7)
    """
    msp.add_line((x1, y1), (x2, y2), dxfattribs={'color': color})


def draw_arc(msp, x, y, radius, start_angle, end_angle, color=7):
    """
    Рисует дугу в modelspace.

    Args:
        msp: Modelspace
        x, y: Центр дуги
        radius: Радиус
        start_angle: Начальный угол (градусы)
        end_angle: Конечный угол (градусы)
        color: Цвет (по умолчанию 7)
    """
    msp.add_arc((x, y), radius=radius, start_angle=start_angle,
                end_angle=end_angle, dxfattribs={'color': color})


def draw_arc_direction(msp, start_x, start_y, end_x, end_y, radius, direction, color=7):
    """
    Рисует дугу по направлению выгиба.

    Args:
        msp: Modelspace
        start_x, start_y: Начальная точка
        end_x, end_y: Конечная точка
        radius: Радиус дуги
        direction: Куда выгибается дуга:
            'up' - вверх
            'down' - вниз
            'left' - влево
            'right' - вправо
        color: Цвет (по умолчанию 7)

    Returns:
        bool: True если дуга нарисована, False если ошибка
    """
    # 1. Находим середину отрезка
    mid_x = (start_x + end_x) / 2
    mid_y = (start_y + end_y) / 2

    # 2. Длина хорды
    dx = end_x - start_x
    dy = end_y - start_y
    chord = math.sqrt(dx ** 2 + dy ** 2)

    # 3. Проверяем радиус
    if radius < chord / 2:
        print(f"⚠ Ошибка: радиус {radius} слишком мал!")
        print(f"  Минимальный радиус: {chord / 2:.2f}")
        return False

    # 4. Находим высоту сегмента
    height = math.sqrt(radius ** 2 - (chord / 2) ** 2)

    # 5. Вектор вдоль хорды
    vx = dx / chord
    vy = dy / chord

    # 6. В зависимости от направления находим центр
    if direction == 'up':
        px, py = -vy, vx  # перпендикуляр влево
        if vy > 0:  # если линия идет вверх
            px, py = -px, -py  # инвертируем
    elif direction == 'down':
        px, py = vy, -vx  # перпендикуляр вправо
        if vy < 0:  # если линия идет вниз
            px, py = -px, -py
    elif direction == 'left':
        px, py = -vy, vx
    elif direction == 'right':
        px, py = vy, -vx
    else:
        print(f"⚠ Неизвестное направление: {direction}")
        print("  Используйте: 'up', 'down', 'left', 'right'")
        return False

    # 7. Находим центр дуги
    center_x = mid_x + px * height
    center_y = mid_y + py * height

    # 8. Находим углы начальной и конечной точек
    angle1 = math.degrees(math.atan2(start_y - center_y, start_x - center_x))
    angle2 = math.degrees(math.atan2(end_y - center_y, end_x - center_x))

    # Корректируем углы (0-360 градусов)
    if angle1 < 0:
        angle1 += 360
    if angle2 < 0:
        angle2 += 360

    # 9. Рисуем дугу
    msp.add_arc(
        (center_x, center_y),
        radius,
        angle1,
        angle2,
        dxfattribs={'color': color}
    )

    return True


def draw_circle(msp, x, y, radius, color=7):
    """
    Рисует круг в modelspace.

    Args:
        msp: Modelspace
        x, y: Центр круга
        radius: Радиус
        color: Цвет (по умолчанию 7)
    """
    msp.add_circle((x, y), radius=radius, dxfattribs={'color': color})


def draw_polyline(msp, points, color=7, close=False):
    """
    Рисует полилинию по точкам.

    Args:
        msp: Modelspace
        points: Список точек [(x1,y1), (x2,y2), ...]
        color: Цвет (по умолчанию 7)
        close: Замкнуть полилинию (по умолчанию False)
    """
    msp.add_lwpolyline(points, dxfattribs={'color': color}, close=close)


def draw_rectangle(msp, x0, y0, x1, y1, color=7):
    """
    Рисует прямоугольник в modelspace по двум точкам (полилинией).

    Args:
        msp: Modelspace
        x0, y0: Нижний левый угол
        x1, y1: Верхний правый угол
        color: Цвет (по умолчанию 7)
    """
    msp.add_lwpolyline(
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        close=True,
        dxfattribs={'color': color}
    )


def save_document(doc, filepath):
    """
    Сохраняет документ в файл.

    Args:
        doc: DXF документ
        filepath: Полный путь к файлу
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    doc.saveas(filepath)
    print(f"✅ Файл сохранен: {filepath}")