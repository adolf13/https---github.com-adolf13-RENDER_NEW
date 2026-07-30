"""
Конфигурация по умолчанию для генерации дверей
Все параметры могут быть переопределены через CLI
"""

# ═══════════════════════════════════════════════════════════════
#  ПАРАМЕТРЫ ПО УМОЛЧАНИЮ (задаются здесь, не в CLI)
# ═══════════════════════════════════════════════════════════════

# Основные параметры
DEFAULT_DOOR_THICKNESS = 0.04  # метры
DEFAULT_CASING_COLOR = (0.5, 0.5, 0.5)
DEFAULT_SIDE = 'R'
# Размеры фурнитуры (в мм)
HANDLE_OFFSET_MM = 84.0
HANDLE_HEIGHT_MM = 996.0
PLATE_OFFSET_Y_MM = -120.0
PLATE_OFFSET_Y_MM2 = 350
LATCH_OFFSET_Y_MM = 150

HANDLE_SCALE = 1  # Масштаб для ручки
PLATE_SCALE = 1  # Масштаб для накладки
LATCH_SCALE = 1  # Масштаб для задвижки

PEEPHOLE_OFFSET_MM = 0.0  # Смещение по X от центра (мм)
PEEPHOLE_HEIGHT_MM = 1500.0  # Высота от нижнего края (мм)
PEEPHOLE_INSET_MM = 120.0  # Отступ от края для side-right (мм)
PEEPHOLE_POS = "center"  # "center", "side-left", "side-right"
PEEPHOLE_SCALE = 1  # Масштаб STL
PEEPHOLE_ROTATION = (0, 0, 0)  # Поворот STL

HINGE_OFFSET_MM = 0  # Отступ от края двери (мм)
HINGE_PROTRUDE_M = 0.005  # Выступ от поверхности (метры)
HINGE_SCALE = 0.001  # Масштаб STL
HINGE_ROTATION_DEG = (90, 0, 180)  # Поворот STL
HINGE_OFFSET_BOTTOM_M = 0.2  # 150 мм от низа
HINGE_OFFSET_TOP_M = 0.2  # 150 мм от верха
HINGE_MIDDLE_OFFSET_FROM_TOP_M = 0.3  # 300 мм
# Кольца петель
HINGE_RING_RADIUS_MM = 10.0  # Радиус кольца (мм)
HINGE_RING_TUBE_MM = 6.0  # Толщина кольца (мм)
HINGE_RING_DX_MM = 0.0  # Смещение кольца по X (мм)
HINGE_RING_DY_MM = 0.0  # Смещение кольца по Y (мм)
HINGE_RING_DZ_MM = 12.0  # Смещение кольца по Z (мм)

# Параметры коробки
FRAME_SCALE = 0.001
FRAME_ROTATION_DEG = (0.0, 90, 180)

# Окружение
CASING_COLOR = (0.75, 0.65, 0.55)
WALL_Z_OFFSET_MM = 100.0
WALL_WIDTH_M = 3.0
WALL_HEIGHT_M = 2.3
WALL_TILE_U = 1.0
WALL_TILE_V = 1.0
FLOOR_WIDTH_M = 3.0
FLOOR_DEPTH_M = 1.0
FLOOR_TILE_U = 1.0
FLOOR_TILE_V = 1.0

# Параметры профиля панелей (из оригинального кода)
PROFILE_Z_MM = [0.0, -4.0, -9.0, -18.0, -18.0, -9.0, -4.0]
CENTER_Z_MM = -4.0
GROOVE_WIDTH_MM = 6.0
GROOVE_RAISE_MM = 3.0