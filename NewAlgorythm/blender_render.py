import bpy
import sys
import math
import os
from mathutils import Vector


# Blender 4.2+: Shade Auto Smooth создаёт модификатор Smooth by Angle.
# Нулевой угол сохраняет плоские участки полотна плоскими и разделяет нормали
# на любом реальном изломе геометрии. Значение можно переопределить на сервере
# переменной окружения DOOR_AUTO_SMOOTH_ANGLE_DEG.
AUTO_SMOOTH_ANGLE_DEGREES = float(
    os.environ.get("DOOR_AUTO_SMOOTH_ANGLE_DEG", "0")
)
DOOR_MATERIAL_KEYWORDS = ("door_front", "door_body")


def object_uses_material(obj, keywords):
    """Проверить назначенные объекту материалы без зависимости от имени OBJ."""
    return any(
        slot.material
        and any(keyword in slot.material.name.lower() for keyword in keywords)
        for slot in obj.material_slots
    )


def load_smooth_by_angle_node_group():
    """Синхронно загрузить штатный asset для headless-режима Blender."""
    node_group_name = "Smooth by Angle"
    existing = bpy.data.node_groups.get(node_group_name)
    if existing is not None:
        return existing

    resource_root = bpy.utils.resource_path('LOCAL')
    asset_candidates = (
        # Blender 4.2 LTS
        os.path.join(
            resource_root,
            "datafiles", "assets", "geometry_nodes", "smooth_by_angle.blend",
        ),
        # Более новые версии Blender с объединённой Essentials-библиотекой
        os.path.join(
            resource_root,
            "datafiles", "assets", "nodes", "geometry_nodes_essentials.blend",
        ),
    )
    for asset_path in asset_candidates:
        if not os.path.isfile(asset_path):
            continue
        with bpy.data.libraries.load(asset_path, assets_only=True) as (data_from, data_to):
            if node_group_name not in data_from.node_groups:
                continue
            data_to.node_groups = [node_group_name]
        loaded = bpy.data.node_groups.get(node_group_name)
        if loaded is not None:
            return loaded

    raise RuntimeError(
        "В установке Blender не найден штатный asset Smooth by Angle. "
        "Установите полную сборку Blender 4.2 LTS вместе с библиотекой Essentials."
    )


def add_smooth_by_angle_from_asset(obj, angle_radians):
    """Добавить тот же модификатор напрямую, если оператор отменён в background."""
    node_group = load_smooth_by_angle_node_group()
    modifier = obj.modifiers.new(name="Smooth by Angle", type='NODES')
    modifier.node_group = node_group

    angle_socket = next(
        (
            item
            for item in node_group.interface.items_tree
            if getattr(item, "item_type", None) == 'SOCKET'
            and getattr(item, "in_out", None) == 'INPUT'
            and getattr(item, "socket_type", None) == 'NodeSocketFloat'
            and item.name == "Angle"
        ),
        None,
    )
    if angle_socket is None:
        obj.modifiers.remove(modifier)
        raise RuntimeError("В asset Smooth by Angle не найден вход Angle")
    modifier[angle_socket.identifier] = angle_radians
    obj.update_tag()
    return modifier


def apply_door_auto_smooth_42(obj, angle_degrees):
    """Добавить Shade Auto Smooth / Smooth by Angle в Blender 4.2+."""
    if bpy.app.version < (4, 2, 0):
        raise RuntimeError(
            "Рендер дверного полотна требует Blender 4.2 или новее; "
            f"запущена версия {bpy.app.version_string}"
        )
    if not 0.0 <= angle_degrees <= 180.0:
        raise ValueError(
            "DOOR_AUTO_SMOOTH_ANGLE_DEG должен быть в диапазоне 0..180, "
            f"получено {angle_degrees}"
        )

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    existing_modifiers = {modifier.as_pointer() for modifier in obj.modifiers}
    result = bpy.ops.object.shade_auto_smooth(
        use_auto_smooth=True,
        angle=math.radians(angle_degrees),
    )
    created_modifiers = [
        modifier
        for modifier in obj.modifiers
        if modifier.as_pointer() not in existing_modifiers
    ]
    smooth_modifier = next(
        (modifier for modifier in reversed(created_modifiers) if modifier.type == 'NODES'),
        None,
    )

    # В 4.2 автосглаживание загружает встроенный asset. Если асинхронный
    # оператор отменён в background, загружаем тот же asset синхронно.
    if 'FINISHED' not in result or smooth_modifier is None:
        for modifier in created_modifiers:
            obj.modifiers.remove(modifier)
        smooth_modifier = add_smooth_by_angle_from_asset(
            obj,
            math.radians(angle_degrees),
        )
        print(f"Shade Auto Smooth operator fallback: result={result}")

    print(
        f"Auto Smooth: {obj.name}, angle={angle_degrees:g}°, "
        f"modifier={smooth_modifier.name}"
    )

argv = sys.argv
argv = argv[argv.index("--") + 1:]
obj_path = argv[0]
output_path = argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
print(f"Blender version: {bpy.app.version_string}")
bpy.ops.wm.obj_import(filepath=obj_path)

objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not objs:
    raise Exception("OBJ not imported")

# Применяем сглаживание выборочно
for obj in objs:
    if obj.type == 'MESH':
        # Объекты, которые НЕ должны иметь искусственного сглаживания
        flat_objects = ['casing', 'wall', 'floor', 'metal_frame']
        is_door_leaf = (
            any(keyword in obj.name.lower() for keyword in DOOR_MATERIAL_KEYWORDS)
            or object_uses_material(obj, DOOR_MATERIAL_KEYWORDS)
        )
        is_flat_object = (
            any(keyword in obj.name.lower() for keyword in flat_objects)
            or object_uses_material(obj, flat_objects)
        )

        if is_door_leaf:
            apply_door_auto_smooth_42(obj, AUTO_SMOOTH_ANGLE_DEGREES)
        else:
            obj.data.shade_smooth()

        # Если это обналичка, стена, пол или металлическая коробка - добавляем EdgeSplit
        if is_flat_object:
            # Добавляем модификатор, который убирает "закругленный" эффект на плоских гранях
            obj.modifiers.new(name='EdgeSplit', type='EDGE_SPLIT')

# --------------------------------------------------
# Свет
# --------------------------------------------------

# Основной — сбоку сверху, рисует тени на гранях
light_data = bpy.data.lights.new(name="MainLight", type='AREA')
light_data.energy = 120
light = bpy.data.objects.new(name="MainLight", object_data=light_data)
bpy.context.collection.objects.link(light)
light.location = (2.5, -1.5, 2.7)
light.scale = (6, 6, 6)

# Заполняющий — с другой стороны, убирает жёсткие тени
fill_data = bpy.data.lights.new(name="FillLight", type='AREA')
fill_data.energy = 40
fill = bpy.data.objects.new(name="FillLight", object_data=fill_data)
bpy.context.collection.objects.link(fill)
fill.location = (-1.5, -1.0, 1.0)
fill.scale = (0.8, 0.8, 0.8)

# Боковой акцентный — подчёркивает горизонтальные грани фрезеровки
accent_data = bpy.data.lights.new(name="AccentLight", type='AREA')
accent_data.energy = 85
accent = bpy.data.objects.new(name="AccentLight", object_data=accent_data)
bpy.context.collection.objects.link(accent)
accent.location = (-2.0, -0.8, 1.5)
accent.scale = (3.0, 3.0, 3.0)

# --------------------------------------------------
# Белый фон
# --------------------------------------------------

world = bpy.data.worlds[0] if bpy.data.worlds else bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.93, 0.93, 0.94, 1)
    bg.inputs[1].default_value = 0.6

# --------------------------------------------------
# Cycles
# --------------------------------------------------

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 64  # 128
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.05  # 0.01
scene.cycles.adaptive_min_samples = 16  # delete? just for optimization
scene.cycles.max_bounces = 3  # 4
scene.cycles.diffuse_bounces = 1  # 2
scene.cycles.glossy_bounces = 1  # 2
scene.cycles.transmission_bounces = 4  # 12
scene.cycles.transparent_max_bounces = 4  # 8
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1920
scene.render.film_transparent = False
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = output_path
scene.render.use_persistent_data = True

# --- Настройка GPU-рендеринга ---
print("\n" + "="*40)
print("Настройка GPU-рендеринга...")

scene.cycles.device = 'CPU' # По умолчанию CPU

try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.get_devices()
    
    # Ищем доступные GPU
    gpu_devices = [d for d in prefs.devices if d.type != 'CPU']
    
    if not gpu_devices:
        print("GPU для Cycles не найдены. Используется CPU.")
    else:
        print(f"Найдено GPU: {len(gpu_devices)}")
        for i, d in enumerate(gpu_devices):
            print(f"  {i}: {d.name} ({d.type})")

        # Выбираем бэкенд: OPTIX предпочтительнее для NVIDIA, затем CUDA
        if 'OPTIX' in [d.type for d in prefs.devices]:
             prefs.compute_device_type = 'OPTIX'
             print("Выбран бэкенд: OPTIX.")
        elif 'CUDA' in [d.type for d in prefs.devices]:
             prefs.compute_device_type = 'CUDA'
             print("Выбран бэкенд: CUDA.")
        else:
            print("Ни OPTIX, ни CUDA не доступны. Используется CPU.")
            raise RuntimeError("Подходящий GPU бэкенд не найден.")

        # Включаем все найденные GPU для рендеринга
        for d in prefs.devices:
            if d.type != 'CPU':
                d.use = True
                print(f"Устройство включено: {d.name}")
            else:
                d.use = False # Явно отключаем CPU

        scene.cycles.device = 'GPU'
        print("Cycles настроен на использование GPU.")

except Exception as e:
    print(f"Ошибка при настройке GPU: {e}")
    print("Откат на CPU-рендеринг.")
    scene.cycles.device = 'CPU'

print("="*40 + "\n")

scene.view_settings.view_transform = 'Standard'
scene.view_settings.exposure = 0.0

# --------------------------------------------------
# Материалы
# --------------------------------------------------

for mat in bpy.data.materials:
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not principled:
        continue

    name = mat.name.lower()

    if 'hw_mirror' in name:
        principled.inputs['Base Color'].default_value = (0.05, 0.06, 0.08, 1.0)
        principled.inputs['Metallic'].default_value = 0.0
        principled.inputs['Roughness'].default_value = 0.0
        if 'Transmission Weight' in principled.inputs:
            principled.inputs['Transmission Weight'].default_value = 1.0
        elif 'Transmission' in principled.inputs:
            principled.inputs['Transmission'].default_value = 1.0
        if 'IOR' in principled.inputs:
            principled.inputs['IOR'].default_value = 1.52
        if 'Specular IOR Level' in principled.inputs:
            principled.inputs['Specular IOR Level'].default_value = 1.0
    elif 'hw_keyhole' in name:
        # Dark translucent glass over the keyhole.
        principled.inputs['Base Color'].default_value = (0.04, 0.04, 0.05, 1.0)
        principled.inputs['Roughness'].default_value = 0.05
        principled.inputs['Alpha'].default_value = 0.2
        if 'Specular IOR Level' in principled.inputs:
            principled.inputs['Specular IOR Level'].default_value = 1.0
        try:
            mat.blend_method = 'BLEND'
            mat.show_transparent_back = False
        except Exception:
            pass
    elif 'hw_ring' in name:
        # Кольца петель всегда хромированные
        principled.inputs['Metallic'].default_value = 1.0
        principled.inputs['Base Color'].default_value = (0.85, 0.85, 0.85, 1.0) # Chrome color
        principled.inputs['Roughness'].default_value = 0.15
    elif any(x in name for x in ('handle', 'plate', 'plate2', 'latch', 'hw_hinge', 'metal_frame')):
        # --- ФУРНИТУРА, ПЕТЛИ И МЕТАЛЛИЧЕСКАЯ КОРОБКА ---
        principled.inputs['Metallic'].default_value = 1.0
        base_color_socket = principled.inputs['Base Color']

        if base_color_socket.is_linked:
            # Если подключена текстура (как у коробки и петель)
            # Устанавливаем шероховатость, чтобы текстура была видна
            principled.inputs['Roughness'].default_value = 0.6
            print(f"  - Обработка '{mat.name}': Металл с текстурой. Roughness=0.6")
        else:
            # Если текстуры нет (как у хромированной фурнитуры)
            # Используем цвет из MTL и задаем шероховатость для хрома
            principled.inputs['Roughness'].default_value = 0.2
            imported_color = base_color_socket.default_value
            print(f"  - Обработка '{mat.name}': Металл без текстуры. Roughness=0.2. Цвет: ({imported_color[0]:.3f}, {imported_color[1]:.3f}, {imported_color[2]:.3f})")
    elif 'peephole' in name:
        # Для глазка ничего не делаем, он должен использовать материалы из своего MTL
        print(f"  - Обработка '{mat.name}': Пропуск, используются материалы из MTL файла.")
        pass


# --------------------------------------------------
# bbox ТОЛЬКО полотна двери
# --------------------------------------------------

door_meshes = []
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    for slot in obj.material_slots:
        mat = slot.material
        if mat and any(keyword in mat.name.lower() for keyword in DOOR_MATERIAL_KEYWORDS):
            door_meshes.append(obj)
            break

if not door_meshes:
    raise Exception("Door meshes not found")

all_coords = []
for obj in door_meshes:
    for corner in obj.bound_box:
        all_coords.append(obj.matrix_world @ Vector(corner))

min_x = min(v.x for v in all_coords)
max_x = max(v.x for v in all_coords)
min_y = min(v.y for v in all_coords)
max_y = max(v.y for v in all_coords)
min_z = min(v.z for v in all_coords)
max_z = max(v.z for v in all_coords)

center = Vector((
    (min_x + max_x) / 2,
    (min_y + max_y) / 2,
    (min_z + max_z) / 2,
))

door_width = max_x - min_x
door_height = max_z - min_z

# --------------------------------------------------
# Камера — та же дистанция что была (3.0),
# но теперь смотрит точно на центр полотна
# --------------------------------------------------

cam_data = bpy.data.cameras.new("Camera")
cam_data.type = 'PERSP'
cam_data.lens = 72
cam_data.clip_start = 0.01
cam_data.clip_end = 100.0

cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam

# Определяем расстояние до камеры в зависимости от стороны
if '_out' in obj_path.lower():
    distance = 5  # Отодвигаем камеру для наружной стороны
else:
    distance = 5  # Стандартное расстояние для внутренней стороны

cam.location = (
    center.x + door_width * 0.7,
    center.y - distance,
    center.z + door_height * 0.06,
)

AIM_UP = door_height * 0.07  # Смещаем точку фокусировки на 5% высоты двери вверх
look_target = Vector((center.x, center.y, center.z + AIM_UP))
direction = look_target - cam.location
rot_quat = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot_quat.to_euler()

#Ключевой скользящий свет проявляет рельеф полотна.
# light.data.energy = 70
# light.location = (
#     center.x + door_width * 1.1,
#     center.y - 1.2,
#     center.z + door_height * 0.25,
# )
# light.scale = (5, 5, 5)

# # Мягкий заполняющий свет.
# fill.data.energy = 30
# fill.location = (
#     center.x - door_width * 0.9,
#     center.y - 1.4,
#     center.z,
# )
# fill.scale = (3, 3, 3)

# # Боковой акцент для горизонтальных граней.
# accent.data.energy = 37
# accent.location = (
#     center.x - door_width * 1.0,
#     center.y - 0.6,
#     center.z + door_height * 0.05,
# )
# accent.scale = (2.5, 2.5, 2.5)

# Верхний свет — освещает верхнюю часть двери
# top_data = bpy.data.lights.new(name="TopLight", type='AREA')
# top_data.energy = 45
# top = bpy.data.objects.new(name="TopLight", object_data=top_data)
# bpy.context.collection.objects.link(top)
# top.location = (center.x, center.y - 1.2, center.z + door_height * 0.9)
# top.scale = (4, 4, 4)

# --------------------------------------------------
# Render
# --------------------------------------------------

bpy.ops.render.render(write_still=True)
print(f"Saved: {output_path}")
