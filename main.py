#!/usr/bin/env python3
"""
Генератор 3D моделей дверей

Примеры запуска:
  python main.py --dxf door.dxf --texture texture.jpg --output result --width 900 --height 2008

  # С металлической коробкой
  python main.py --dxf door.dxf --texture tex.jpg --output result --width 900 --height 2008 --frame_metal --frame_stl frame.stl

  # С полным набором параметров
  python main.py --dxf door.dxf --texture tex.jpg --output result --width 1000 --height 2150 --side L --handle_stl handle.stl --handle_finish brass
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))




import argparse
from dataclasses import dataclass
from typing import Optional, Tuple

import config
from door_builder import DoorBuilder
from obj_exporter import write_obj_with_materials
from render import render_both_sides  # ← ДОБАВИТЬ



@dataclass
class DoorParams:
    """Параметры для генерации двери"""
    # Обязательные параметры (передаются через CLI)
    dxf_path: str
    texture_path: str
    output_path: str
    width: float  # мм
    height: float  # мм
    zff: float
    pff: float
    vff: float

    model: str

    # Опциональные параметры (с значениями по умолчанию из config)
    side: Optional[str] = "R"
    inner: bool = False
    door_thickness: float = config.DEFAULT_DOOR_THICKNESS
    casing_color: Tuple[float, float, float] = config.DEFAULT_CASING_COLOR

    # Фурнитура
    handle_path_out: Optional[str] = None
    nakl_main_lock_out: Optional[str] = None
    nakl_adv_lock_out: Optional[str] = None

    handle_path_in: Optional[str] = None
    nakl_main_lock_in: Optional[str] = None
    nakl_adv_lock_in: Optional[str] = None
    latch_path: Optional[str] = None

    # Глазок
    peephole_path: Optional[str] = None
    peephole_offset: bool = False

    hinge_stl: Optional[str] = None
    hinge_finish: Optional[str] = None # Теперь это путь к текстуре
    hinge_count: int = 2

    # Коробка
    frame_metal: bool = False
    frame_stl: Optional[str] = None
    frame_finish: str = "steel"
    frame_inner_finish: Optional[str] = None # Текстура для внутренней части коробки
    frame_texture: Optional[str] = None

    # Окружение
    wall_texture_path: Optional[str] = None
    floor_texture_path: Optional[str] = None

    # Внутренняя сторона (опционально)
    dxf_path_inner: Optional[str] = None
    texture_path_inner: Optional[str] = None
    wall_texture_path_inner: Optional[str] = None
    floor_texture_path_inner: Optional[str] = None

    def __post_init__(self):
        """Заполняем внутреннюю сторону, если не задана"""
        if self.dxf_path_inner is None:
            self.dxf_path_inner = self.dxf_path
        if self.texture_path_inner is None:
            self.texture_path_inner = self.texture_path
        if self.wall_texture_path_inner is None:
            self.wall_texture_path_inner = self.wall_texture_path
        if self.floor_texture_path_inner is None:
            self.floor_texture_path_inner = self.floor_texture_path


def generate_door(params: DoorParams):
    """
    Генерирует 3D модель двери с автоматическим рендерингом

    Args:
        params: Параметры двери
    """
    print(f"\n{'=' * 60}")
    print(f"🚪 Генерация двери: {params.output_path}")
    print(f"   Размер: {params.width}×{params.height} мм")
    print(f"   Сторона: {params.side}")
    print(f"   DXF: {params.dxf_path}")
    print(f"{'=' * 60}\n")

    # Создаем выходные папки
    os.makedirs(os.path.dirname(params.output_path) or '.', exist_ok=True)

    # Генерируем внешнюю и внутреннюю стороны
    sides = [
        ("out", False, params.dxf_path, params.texture_path,
         params.wall_texture_path, params.floor_texture_path),
        ("in", True, params.dxf_path_inner, params.texture_path_inner,
         params.wall_texture_path_inner, params.floor_texture_path_inner),
    ]

    results = {}

    for tag, inner, dxf_path, tex_path, wall_tex, floor_tex in sides:
        print(f"\n📐 Обработка {'внутренней' if inner else 'внешней'} стороны...")

        # 1. Загружаем DXF
        if not os.path.exists(dxf_path):
            print(f"❌ DXF не найден: {dxf_path}")
            continue
        from dxf_processor import DXFProcessor # Импортируем здесь, чтобы избежать циклической зависимости

        processor = DXFProcessor(dxf_path)
        if not processor.load():
            print(f"❌ Не удалось загрузить DXF: {dxf_path}")
            continue

        dxf_data = processor.extract_geometry()

        # 2. Создаем конфигурацию для Builder
        builder_params = {
            "dxf_data": dxf_data,
            "params": params,
            "inner": inner,
            "wall_texture_path": wall_tex,
            "floor_texture_path": floor_tex,
            "texture_path": tex_path,
        }

        # 3. Строим модель
        builder = DoorBuilder(**builder_params)
        meshes = builder.build()

        # 4. Подготавливаем материалы
        material_props = builder.get_material_props()

        print(f"\n📦 Материалы для {tag}:")
        for mat_name, props in material_props.items():
            print(f"  {mat_name}: текстура={props.get('texture')}")

        # 5. Экспортируем
        obj_path = f"{params.output_path}_{tag}.obj"
        write_obj_with_materials(obj_path, meshes, material_props)

        # 6. Статистика
        w, h = builder.door_width * 1000, builder.door_height * 1000
        print(f"\n✅ Готово: {obj_path}")
        print(f"   Размер: {w:.0f}×{h:.0f} мм")
        print(f"   Мешей: {len(meshes)}")

        results[tag] = (builder.door_width, builder.door_height)

    # 7. АВТОМАТИЧЕСКИЙ РЕНДЕРИНГ
    if results:
        print(f"\n{'=' * 60}")
        print("🎨 Запуск автоматического рендеринга...")
        print(f"{'=' * 60}")

        out_success, in_success = render_both_sides(params.output_path)

        if out_success:
            print(f"✅ Рендер внешней: {params.output_path}_out.png")
        if in_success:
            print(f"✅ Рендер внутренней: {params.output_path}_in.png")
        if not out_success and not in_success:
            print("⚠️ Рендеринг не выполнен (Blender не найден или ошибка)")

    return results


def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description="Генератор 3D моделей дверей",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Базовая генерация
  python main.py --dxf door.dxf --texture tex.jpg --output result --width 900 --height 2008

  # С металлической коробкой
  python main.py --dxf door.dxf --texture tex.jpg --output result --width 900 --height 2008 --frame_metal --frame_stl frame.stl

  # С полным набором параметров
  python main.py --dxf door.dxf --texture tex.jpg --output result --width 1000 --height 2150 --side L --handle_stl handle.stl --handle_finish brass --frame_metal --frame_stl frame.stl --frame_finish steel
"""
    )

    # Обязательные параметры
    parser.add_argument('--dxf', required=True, help='Путь к DXF файлу')
    parser.add_argument('--texture', required=True, help='Путь к текстуре')
    parser.add_argument('--output', required=True, help='Путь для сохранения')
    parser.add_argument('--width', required=True, type=float, help='Ширина двери в мм')
    parser.add_argument('--height', required=True, type=float, help='Высота двери в мм')

    # Опциональные параметры
    parser.add_argument('--side', default=config.DEFAULT_SIDE, choices=['L', 'R'],
                        help='Сторона открывания (L/R)')

    # Фурнитура
    parser.add_argument('--handle_path', help='Путь к файлу ручки (OBJ/STL)')
    parser.add_argument('--peephole_path', help='Путь к файлу глазка (OBJ/STL)')
    parser.add_argument('--peephole_pos', default='center',
                        choices=['center', 'side-left', 'side-right'],
                        help='Позиция глазка')
    parser.add_argument('--plate_path', help='Путь к файлу накладки (OBJ/STL)')

    parser.add_argument('--plate_path2', help='Путь к файлу накладки 2 (OBJ/STL)')

    parser.add_argument('--latch_path', help='Путь к файлу задвижки (OBJ/STL)')



    # Петли
    parser.add_argument('--hinge_stl', help='STL петли')
    parser.add_argument('--hinge_finish', default='chrome',
                        help='Отделка петель')
    parser.add_argument('--hinge_count', type=int, default=2,
                        choices=[2, 3], help='Количество петель (2 или 3)')

    # Коробка
    parser.add_argument('--frame_metal', action='store_true',
                        help='Использовать металлическую коробку')
    parser.add_argument('--frame_stl', help='STL металлической коробки')
    parser.add_argument('--frame_finish',
                        help='Отделка коробки')
    parser.add_argument('--frame_inner_finish', help='Отделка внутренней части коробки')
    parser.add_argument('--frame_texture', help='Текстура для коробки')

    # Окружение
    parser.add_argument('--wall_texture', help='Текстура стены')
    parser.add_argument('--floor_texture', help='Текстура пола')

    # Внутренняя сторона
    parser.add_argument('--dxf_inner', help='DXF для внутренней стороны')
    parser.add_argument('--texture_inner', help='Текстура для внутренней стороны')
    parser.add_argument('--wall_texture_inner', help='Текстура стены (внутри)')
    parser.add_argument('--floor_texture_inner', help='Текстура пола (внутри)')

    # Рендеринг
    parser.add_argument('--render', action='store_true',
                        help='Запустить рендеринг в Blender после генерации')
    parser.add_argument('--blender_exe', help='Путь к Blender.exe')

    return parser.parse_args()


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Строим абсолютные пути
    base_dir = current_dir  # или os.path.join(current_dir, '3D_module')
    
    def to_obj_path(path):
        if path and path.lower().endswith('.stl'):
            return path[:-4] + '.obj'
        # Если в пути есть .obj, но он заканчивается на .stl (ошибка в GUI), исправляем
        if path and '.obj' in path and path.lower().endswith('.stl'):
             return path[:-4]
        if path and '.stl' in path and path.lower().endswith('.obj'):
             return path
        return path

    params = DoorParams(
        dxf_path=os.path.join(base_dir, "Pic/D26_out.dxf"),
        texture_path=os.path.join(base_dir, "textures/ЛКП_Зеленый изумруд-Ч.jpg"),
        output_path=os.path.join(base_dir, "result/door"),
        width=950,
        height=2050,
        pff=85,
        zff=85,
        vff=85,
        side="R",
        hinge_stl=os.path.join(base_dir, "furniture/pelta.stl"),
        hinge_finish=os.path.join(base_dir, "textures/Черная-шагрень-Ч.jpg"),
        hinge_count=3,
        
        handle_path_out=to_obj_path(os.path.join(base_dir, "furniture/handle_LARGO_cr.obj")),
        
        peephole_path=to_obj_path(os.path.join(base_dir, "furniture/peep.obj")),
        peephole_pos="center",
        
        nakl_main_lock_out=to_obj_path(os.path.join(base_dir, "furniture/BN_26_cr.obj")),
        
        nakl_adv_lock_out=to_obj_path(os.path.join(base_dir, "furniture/Nakl_Krit_cr.obj")),
        
        latch_path=to_obj_path(os.path.join(base_dir, "furniture/Pov_Apecs_bl.obj")),
        
        frame_metal=False,
        frame_stl=os.path.join(base_dir, "frame/DELTA/Gasparini_E5_H2100_B950.stl"),
        frame_finish=os.path.join(base_dir, "textures/Черная-шагрень-Ч.jpg"),
        frame_inner_finish=os.path.join(base_dir, "textures/Черная-шагрень-Ч.jpg"),
        wall_texture_path=os.path.join(base_dir, "decor/wall3.jpg"),
        floor_texture_path=os.path.join(base_dir, "decor/floor.jpg"),
        dxf_path_inner=os.path.join(base_dir, "Pic/D26_in.dxf"),
        texture_path_inner=os.path.join(base_dir, "textures/ЛКП_Зеленый изумруд-Ч.jpg"),
        wall_texture_path_inner=os.path.join(base_dir, "decor/wall.jpg"),
        floor_texture_path_inner=os.path.join(base_dir, "decor/floor.jpg")
    )

    generate_door(params)