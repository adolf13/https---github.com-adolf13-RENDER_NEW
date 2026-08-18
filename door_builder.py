"""
Построитель 3D модели двери
"""
import os
import numpy as np
import open3d as o3d
from typing import List, Tuple, Optional
import config
from dxf_processor import DXFData
from geometry import make_door_front_plain, make_groove_meshes, reconstruct_panel_rects, group_rects_into_panels, make_door_front_with_holes, make_raised_panel_meshes, make_metal_frame, make_wall, make_floor, bbox, rot, make_casing_bar, make_flat_quad


class DoorBuilder:
    """Построитель 3D модели двери"""

    def __init__(self, dxf_data: DXFData, params, inner: bool = False,
                 wall_texture_path: Optional[str] = None,
                 floor_texture_path: Optional[str] = None,
                 texture_path: Optional[str] = None):

        self.dxf_data = dxf_data
        self.params = params
        self.inner = inner
        self.scale = 0.001
        self.door_thickness = params.door_thickness

        # Размеры
        self.door_width = params.width * self.scale
        self.door_height = params.height * self.scale
        
        self.pff=params.pff
        self.zff=params.zff
        self.vff=params.vff



        # Координаты
        self.min_x = -params.width / 2
        self.max_x = params.width / 2
        self.min_y = -params.height / 2
        self.max_y = params.height / 2

        # Сторона
        self.side = params.side.upper()
        if self.inner:
            self.side = "L" if self.side == "R" else "R"

        # Стена
        self._z_wall = 0.031 + (config.WALL_Z_OFFSET_MM * 0.001 if self.inner else 0.0)

        # Текстура двери
        self.texture_path = texture_path

        # Текстура для наличника (только для внешней стороны)
        self.casing_texture = params.frame_finish if not inner else None

        # Коробка - используем get_finish_props
        self.frame_texture_path = params.frame_inner_finish if self.inner and params.frame_inner_finish else params.frame_finish

        # Петли - используем get_finish_props
        self.hinge_texture_path = params.hinge_finish

        # Текстуры окружения
        self.wall_texture_path = wall_texture_path
        self.floor_texture_path = floor_texture_path

        print(f"\n🔧 Инициализация DoorBuilder:")
        print(f"  frame_finish: {params.frame_finish}")
        print(f"  hinge_finish: {self.hinge_texture_path}")

    def build(self) -> List[Tuple[o3d.geometry.TriangleMesh, str, Optional[str]]]:
        """Собирает все меши двери"""
        meshes = []

        # Получаем линии панелей
        panel_lines_raw = [
            (ln.start.x, ln.start.y, ln.end.x, ln.end.y)
            for ln in self.dxf_data.entities.get('line', [])
            if ln.layer.upper() == 'PANEL'
        ]

        panel_type = self.dxf_data.panel_type
        print(f"🎨 panel_type={panel_type}, PANEL lines={len(panel_lines_raw)}")

        # 1. Корпус двери
        meshes.append((self._make_body(), "door_body", None))

        # 2. Панели и передняя грань
        if panel_type == 'groove':
            front = make_door_front_plain(
                self.door_width, self.door_height, self.door_thickness,
                self.texture_path
            )
            meshes.append((front, "door_front", self.texture_path))

            grooves = make_groove_meshes(
                panel_lines_raw, self.scale, self.door_thickness,
                self.min_x, self.min_y, self.door_width, self.door_height
            )
            print(f"📐 Валиков (grooves): {len(grooves)}")
            for gm in grooves:
                meshes.append((gm, "door_front", self.texture_path))
        else:
            rects = reconstruct_panel_rects(panel_lines_raw)
            groups = group_rects_into_panels(rects)
            print(f"📐 Панельных групп: {len(groups)}, рамок: {len(rects)}")

            front = make_door_front_with_holes(
                self.door_width, self.door_height, self.door_thickness,
                groups, self.scale, self.min_x, self.min_y, self.texture_path
            )
            if front:
                meshes.append((front, "door_front", self.texture_path))

            for pm in make_raised_panel_meshes(
                    groups, self.scale, self.door_thickness,
                    self.min_x, self.min_y, self.door_width, self.door_height
            ):
                meshes.append((pm, "door_front", self.texture_path))

        # 3. Фурнитура
        if self.inner:
            # Внутренняя сторона
            if self.params.handle_path_in:
                meshes.append(self._make_handle(self.params.handle_path_in, "handle_in"))
            if self.params.nakl_main_lock_in:
                meshes.append(self._make_plate(self.params.nakl_main_lock_in, "nakl_main_lock_in"))
            if self.params.nakl_adv_lock_in:
                meshes.append(self._make_plate2(self.params.nakl_adv_lock_in, "nakl_adv_lock_in"))
            if self.params.latch_path:
                latch_items = self._make_latch()
                if latch_items:
                    for p, kind, path in latch_items:
                        print(f"🔒 Задвижка: используется файл {path}")
                        mat_name = "latch"
                        meshes.append((p, mat_name, path))
        else:
            # Внешняя сторона
            if self.params.handle_path_out:
                meshes.append(self._make_handle(self.params.handle_path_out, "handle_out"))
            if self.params.nakl_main_lock_out:
                meshes.append(self._make_plate(self.params.nakl_main_lock_out, "nakl_main_lock_out"))
            if self.params.nakl_adv_lock_out:
                meshes.append(self._make_plate2(self.params.nakl_adv_lock_out, "nakl_adv_lock_out"))

        # Глазок =================================================
        if self.params.peephole_path:
            peephole_items = self._make_peephole()
            if peephole_items:
                for p, kind, path in peephole_items:
                    print(f"👁️ Глазок: используется файл {path or self.params.peephole_path}")
                    # Линзе назначаем зеркальный материал, остальному — ничего (используются из OBJ)
                    mat_name = "hw_mirror" if kind == "mirror" else "peephole"
                    meshes.append((p, mat_name, path))

        # 4. Петли (только для внешней стороны)
        if self.params.hinge_stl and not self.inner:
            hinge_items = self._make_hinges()
            if hinge_items:
                for hg, kind in hinge_items:
                    # Кольца всегда 'hw_ring', петли всегда 'hw_hinge'
                    # Текстуры для них назначаются в get_material_props
                    mat = "hw_ring" if kind == "ring" else "hw_hinge" 
                    meshes.append((hg, mat, None))

        # 5. Коробка/наличник
        if self.params.frame_metal or self.inner:
            frame_mesh = make_metal_frame(
                frame_stl_path=self.params.frame_stl, door_width=self.door_width, door_height=self.door_height,
                door_thickness=self.door_thickness,
                frame_scale=config.FRAME_SCALE, texture_path=self.frame_texture_path, 
                frame_rotation_deg=config.FRAME_ROTATION_DEG,
                extra_y_180=self.inner,
                z_offset=(config.WALL_Z_OFFSET_MM * 0.001 if self.inner else 0.0))
            
            if frame_mesh:
                print("🔩 Коробка: металлическая (STL)")
                meshes.append((frame_mesh, "metal_frame", None))
            else:
                print("⚠ STL коробки не загружен — fallback на простой наличник")
                for cp in self._make_casing():
                    meshes.append((cp, "casing", self.frame_texture_path))
        else:
            print(f"🪵 Наличник: деревянный")
            # Передаем текстуру напрямую, чтобы сгенерировать UV-координаты
            meshes.extend(self._make_casing(self.casing_texture))

        # 6. Стена и пол
        meshes.append((make_wall(
            self.door_width, self.door_height, self.door_thickness,
            wall_width_m=config.WALL_WIDTH_M,
            wall_height_m=config.WALL_HEIGHT_M,
            wall_texture_path=self.wall_texture_path,
            tile_u=config.WALL_TILE_U,
            tile_v=config.WALL_TILE_V,
            z=self._z_wall,
        ), "env_wall", self.wall_texture_path))

        meshes.append((make_floor(
            self.door_width, self.door_height, self.door_thickness,
            floor_width_m=config.FLOOR_WIDTH_M,
            floor_depth_m=config.FLOOR_DEPTH_M,
            floor_texture_path=self.floor_texture_path,
            tile_u=config.FLOOR_TILE_U,
            tile_v=config.FLOOR_TILE_V,
        ), "env_floor", self.floor_texture_path))

        return meshes

    def get_material_props(self) -> dict:
        """Возвращает свойства материалов для экспорта"""
        props = {}

        # --- Наличник (casing) ---
        props["casing"] = {
            "texture": self.casing_texture,
        }
        print(f"📦 Наличник: текстура={self.casing_texture}")

        # --- Панель (door_front) ---
        props["door_front"] = {
            "color": (0.8, 0.8, 0.8),
            "Ks": (0.1, 0.1, 0.1),
            "Ns": 10.0,
            "texture": self.texture_path if self.texture_path else None,
        }

        # --- Коробка (metal_frame) ---
        props["metal_frame"] = {
            "texture": self.frame_texture_path, # Назначаем текстуру для металлической коробки
        }
        print(f"📦 Коробка: используется текстура {self.frame_texture_path}")

        # --- Петли (hw_hinge) ---
        # Назначаем текстуру для петель
        props["hw_hinge"] = {
            "texture": self.hinge_texture_path,
        }
        print(f"📦 Петли: используется текстура {self.hinge_texture_path}")

        # --- Глазок (если нет MTL) ---
        props["hw_peephole"] = {
            "texture": self.hinge_texture_path, # Исправлено: должен быть цвет петель/металла
        }

        # --- Кольцо петли ---
        # Кольца всегда хромированные, текстура не нужна
        props["hw_ring"] = {
            "texture": None,
        }

        # --- Скважина ---
        props["hw_keyhole"] = {
            "color": (0.05, 0.05, 0.06),
            "Ks": (0.5, 0.5, 0.5),
            "Ns": 120.0,
            "texture": None,
        }

        # --- Фурнитура ---
        # Убираем все свойства. Материалы должны браться только из MTL-файлов фурнитуры.
        props["handle_out"] = {}
        props["nakl_main_lock_out"] = {}
        props["nakl_adv_lock_out"] = {}
        props["handle_in"] = {}
        props["nakl_main_lock_in"] = {}
        props["nakl_adv_lock_in"] = {}
        props["latch"] = {}
        props["peephole"] = {}


        # Отладка
        print(f"\n📦 Материалы для экспорта:")
        for name, data in props.items():
            texture = data.get('texture', None)
            print(f"  {name}: текстура={texture}")

        return props

    # ... остальные методы (_make_body, _make_handle, _make_peephole и т.д.) остаются без изменений ...

    def _make_body(self):
        """Создает корпус двери"""
        w, h, t = self.door_width, self.door_height, self.door_thickness
        verts = np.array([
            [0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0],
            [0, 0, t], [w, 0, t], [w, h, t], [0, h, t],
        ], dtype=np.float64)
        tris = np.array([
            [0, 2, 1], [0, 3, 2], [0, 1, 5], [0, 5, 4],
            [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6],
            [3, 0, 4], [3, 4, 7],
        ], dtype=np.int32)
        m = o3d.geometry.TriangleMesh()
        m.vertices = o3d.utility.Vector3dVector(verts)
        m.triangles = o3d.utility.Vector3iVector(tris)
        m.paint_uniform_color([0.85, 0.75, 0.65])
        m.compute_vertex_normals()
        return m

    def _make_handle(self, obj_path: str, material_name: str):
        """Создает ручку из OBJ файла."""
        # --- Определение координат из INI файла ---
        x_pos_mm = None
        y_pos_mm = None
        try:
            import configparser
            parser = configparser.ConfigParser()
            config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'MakePanel', 'CONFIG'))
            config_path = os.path.join(config_dir, f"{self.params.model}.ini")
            section = 'lock_in' if self.inner else 'lock_out'

            if os.path.exists(config_path):
                parser.read(config_path)
                if parser.has_section(section):
                    x_pos_mm = parser.getfloat(section, 'x_cent', fallback=None)
                    y_pos_mm = parser.getfloat(section, 'y_cent', fallback=None)
                    print(f"🔩 {material_name}: координаты ({x_pos_mm}, {y_pos_mm}) взяты из '{config_path}' секция [{section}]")
        except Exception as e:
            print(f"⚠️ Ошибка при чтении INI для ручки: {e}")

        # Если координаты не найдены, используем значения по умолчанию
        if x_pos_mm is None:
            x_pos_mm = config.HANDLE_OFFSET_MM
            print(f"🔩 {material_name}: используется x_pos по умолчанию {x_pos_mm} мм")
        if y_pos_mm is None:
            y_pos_mm = config.HANDLE_HEIGHT_MM
            print(f"🔩 {material_name}: используется y_pos по умолчанию {y_pos_mm} мм")

        # Константы и загрузка
        model_scale_factor = config.HANDLE_SCALE
        z_offset = 0.01
        print(f"🔩 {material_name}: используется файл {obj_path}")

        m = o3d.io.read_triangle_mesh(obj_path, True)
        if m.is_empty():
            print(f"Не удалось загрузить OBJ: {obj_path}")
            return None

        # --- Трансформации ---
        mn, mx = bbox(m)
        m.translate([0, -(mn[1] + mx[1]) / 2, 0])
        m.scale(model_scale_factor, center=[0, 0, 0])

        if self.side == "L":
            # Зеркалим геометрию ручки для левой стороны
            m.transform(np.array([[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]))

        mn2, _ = bbox(m)
        m.translate([0, 0, self.door_thickness - mn2[2] + z_offset])

        xp = x_pos_mm * self.scale if self.side == "R" else self.door_width - (x_pos_mm * self.scale)
        m.translate([xp, y_pos_mm * self.scale, 0])

        m.compute_vertex_normals()
        return m, material_name, obj_path

    def _make_peephole(self):
        """Создает глазок из OBJ файла, используя координаты из INI-файла модели."""
        # Константы
        scale_factor = config.PEEPHOLE_SCALE
        z_offset = 0.005

        # --- Определение высоты глазка из INI файла ---
        height_y = None
        side_inset_mm = None

        try:
            import configparser
            parser = configparser.ConfigParser()
            # Путь к папке с конфигами относительно этого файла
            config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'MakePanel', 'CONFIG'))
            config_path = os.path.join(config_dir, f"{self.params.model}.ini")
            section = 'peep_in' if self.inner else 'peep_out'

            if os.path.exists(config_path):
                parser.read(config_path)
                if parser.has_section(section) and parser.has_option(section, 'size_from_down'):
                    height_y_mm = parser.getfloat(section, 'size_from_down')
                    height_y = height_y_mm * 0.001  # Переводим в метры
                    print(f"👁️ Глазок: высота {height_y_mm} мм взята из '{config_path}' секция [{section}]")
                
                if self.params.peephole_offset and parser.has_section(section) and parser.has_option(section, 'side_peephole'):
                    side_inset_mm = parser.getfloat(section, 'side_peephole')
                    print(f"👁️ Глазок: боковой отступ {side_inset_mm} мм взят из '{config_path}' секция [{section}]")

        except Exception as e:
            print(f"⚠️ Ошибка при чтении INI для глазка: {e}")

        # Если высота не была найдена в INI, используем значение по умолчанию
        if height_y is None:
            height_y = config.PEEPHOLE_HEIGHT_MM * 0.001
            print(f"👁️ Глазок: используется высота по умолчанию {config.PEEPHOLE_HEIGHT_MM} мм")
        
        # Если боковой отступ не найден в INI, используем значение по умолчанию
        if self.params.peephole_offset and side_inset_mm is None:
            side_inset_mm = config.PEEPHOLE_INSET_MM
            print(f"👁️ Глазок: используется боковой отступ по умолчанию {side_inset_mm} мм")

        # Загрузка OBJ
        obj_path = self.params.peephole_path # Теперь ожидаем .obj
        m = o3d.io.read_triangle_mesh(obj_path, True)
        if m.is_empty():
            print(f"Не удалось загрузить OBJ: {obj_path}")
            return None

        # 1. Центрируем и поворачиваем
        mn, mx = bbox(m)
        m.translate(-(np.array(mn) + np.array(mx)) / 2)
        rot(m, *config.PEEPHOLE_ROTATION)

        # 2. Масштабируем
        m.scale(scale_factor, center=[0, 0, 0])

        # 3. Позиционируем по Z
        _, mx2 = bbox(m)
        m.translate([0, 0, (self.door_thickness + z_offset) - mx2[2]])

        # 4. Позиционируем по XY
        if not self.params.peephole_offset:
            # Если флаг смещения НЕ установлен - ставим по центру
            xp = self.door_width / 2
            print("👁️ Глазок: позиционирование по центру.")
        else:
            # Если флаг смещения установлен - используем боковой отступ
            inset_x = side_inset_mm * 0.001
            xp = self.door_width - inset_x if self.side == 'L' else inset_x
            print(f"👁️ Глазок: позиционирование сбоку (сторона: {self.side}, отступ: {inset_x*1000:.1f} мм).")
        m.translate([xp, height_y, 0])

        m.compute_vertex_normals()

        # 5. Внутренняя сторона
        if self.inner:
            pivot = np.array([xp, height_y, self.door_thickness])
            Rflip = o3d.geometry.get_rotation_matrix_from_xyz(np.radians([0.0, 180.0, 0.0]))
            m.rotate(Rflip, center=pivot)
            _, mx_in = bbox(m)
            m.translate([0.0, 0.0, self.door_thickness + z_offset - mx_in[2]])
            m.compute_vertex_normals()
            return [(m, None, obj_path)]

        # 6. Внешняя сторона (добавляем линзу)
        mirror_radius = 17.0 * 0.001
        mirror_depth = 1.0 * 0.0005
        mirror_dz = -1.2 * 0.001

        _, peephole_max = bbox(m)
        mirror = o3d.geometry.TriangleMesh.create_sphere(radius=mirror_radius, resolution=32)
        mirror.scale(0.4, center=[0, 0, 0])
        mirror.translate([xp, height_y, peephole_max[2] + mirror_depth + mirror_dz])
        mirror.paint_uniform_color([0.95, 0.95, 0.95])
        mirror.compute_vertex_normals()

        print("👁️ Глазок: используются материалы из MTL.")
        return [(m, None, obj_path), (mirror, "mirror", None)]

    def _make_plate(self, obj_path: str, material_name: str):
        """Создает накладку из OBJ файла."""
        # --- Определение координат из INI файла ---
        x_pos_mm = None
        y_pos_mm = None
        try:
            import configparser
            parser = configparser.ConfigParser()
            config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'MakePanel', 'CONFIG'))
            config_path = os.path.join(config_dir, f"{self.params.model}.ini")
            section = 'lock_in' if self.inner else 'lock_out'

            if os.path.exists(config_path):
                parser.read(config_path)
                if parser.has_section(section):
                    x_pos_mm = parser.getfloat(section, 'x_cent', fallback=None)
                    y_cent_mm = parser.getfloat(section, 'y_cent', fallback=None)
                    size_to_fig2_mm = parser.getfloat(section, 'size_to_fig2', fallback=None)
                    if y_cent_mm is not None and size_to_fig2_mm is not None:
                        y_pos_mm = y_cent_mm - size_to_fig2_mm
                    print(f"🔩 {material_name}: координаты ({x_pos_mm}, {y_pos_mm}) взяты из '{config_path}' секция [{section}]")
        except Exception as e:
            print(f"⚠️ Ошибка при чтении INI для накладки: {e}")

        # Если координаты не найдены, используем значения по умолчанию
        if x_pos_mm is None:
            x_pos_mm = config.HANDLE_OFFSET_MM
            print(f"🔩 {material_name}: используется x_pos по умолчанию {x_pos_mm} мм")
        if y_pos_mm is None:
            y_pos_mm = config.HANDLE_HEIGHT_MM + config.PLATE_OFFSET_Y_MM
            print(f"🔩 {material_name}: используется y_pos по умолчанию {y_pos_mm} мм")

        # Загрузка и константы
        model_scale_factor = config.PLATE_SCALE
        z_offset = 0.001
        print(f"🔩 {material_name}: используется файл {obj_path}")
        
        m = o3d.io.read_triangle_mesh(obj_path, True)
        if m.is_empty():
            print(f"Не удалось загрузить OBJ: {obj_path}")
            return None

        # --- Трансформации ---
        mn, mx = bbox(m)
        m.translate([-(mn[0] + mx[0]) / 2, 0, 0])
        m.scale(model_scale_factor, center=[0, 0, 0])

        mn2, _ = bbox(m)
        m.translate([0, 0, self.door_thickness - mn2[2] + z_offset])

        xp = x_pos_mm * self.scale if self.side == "R" else self.door_width - (x_pos_mm * self.scale)
        m.translate([xp, y_pos_mm * self.scale, 0])

        m.compute_vertex_normals()
        return m, material_name, obj_path

    def _make_latch(self):
        """Создает задвижку из OBJ файла (только для внутренней стороны)."""
        # Константы
        # --- Определение координат из INI файла ---
        x_pos_mm = None
        y_pos_mm = None
        try:
            import configparser
            parser = configparser.ConfigParser()
            config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'MakePanel', 'CONFIG'))
            config_path = os.path.join(config_dir, f"{self.params.model}.ini")
            
            if os.path.exists(config_path):
                parser.read(config_path)
                if parser.has_section('latch_in') and parser.has_section('lock_in'):
                    x_pos_mm = parser.getfloat('latch_in', 'x_cent', fallback=None)
                    y_cent_lock_mm = parser.getfloat('lock_in', 'y_cent', fallback=None)
                    from_y_cent_latch_mm = parser.getfloat('latch_in', 'from_y_cent', fallback=None)
                    if y_cent_lock_mm is not None and from_y_cent_latch_mm is not None:
                        y_pos_mm = y_cent_lock_mm + from_y_cent_latch_mm
                    print(f"🔩 Задвижка: координаты ({x_pos_mm}, {y_pos_mm}) взяты из '{config_path}'")
        except Exception as e:
            print(f"⚠️ Ошибка при чтении INI для задвижки: {e}")

        # Если координаты не найдены, используем значения по умолчанию
        if x_pos_mm is None:
            x_pos_mm = config.HANDLE_OFFSET_MM
            print(f"🔩 Задвижка: используется x_pos по умолчанию {x_pos_mm} мм")
        if y_pos_mm is None:
            y_pos_mm = config.HANDLE_HEIGHT_MM + config.LATCH_OFFSET_Y_MM
            print(f"🔩 Задвижка: используется y_pos по умолчанию {y_pos_mm} мм")

        # Загрузка и константы
        model_scale_factor = config.LATCH_SCALE
        z_offset =-0.05
        obj_path = self.params.latch_path # Теперь ожидаем .obj
        m = o3d.io.read_triangle_mesh(obj_path, True)
        if m.is_empty():
            print(f"Не удалось загрузить OBJ: {obj_path}")
            return None

        # --- Трансформации ---
        mn, mx = bbox(m)
        m.translate([-(mn[0] + mx[0]) / 2, 0, 0])
        rot(m, 0, 0, 0)
        m.scale(model_scale_factor, center=[0, 0, 0])

        mn2, _ = bbox(m)
        m.translate([0, 0, self.door_thickness - mn2[2] + z_offset])

        xp = x_pos_mm * self.scale if self.side == "R" else self.door_width - (x_pos_mm * self.scale)
        m.translate([xp, y_pos_mm * self.scale, 0])

        m.compute_vertex_normals()
        return [(m, "latch", obj_path)]

    def _make_plate2(self, obj_path: str, material_name: str):
        """Создает вторую накладку из OBJ файла."""
        # Константы
        # --- Определение координат из INI файла ---
        x_pos_mm = None
        y_pos_mm = None
        try:
            import configparser
            parser = configparser.ConfigParser()
            config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'MakePanel', 'CONFIG'))
            config_path = os.path.join(config_dir, f"{self.params.model}.ini")
            lock_section = 'lock_in' if self.inner else 'lock_out' # e.g., lock_out
            adv_section = 'adv_in' if self.inner else 'adv_out'     # e.g., adv_out

            if os.path.exists(config_path):
                parser.read(config_path)
                if parser.has_section(lock_section) and parser.has_section(adv_section):
                    x_pos_mm = parser.getfloat(adv_section, 'x_cent', fallback=None)
                    y_cent_lock_mm = parser.getfloat(lock_section, 'y_cent', fallback=None)
                    from_y_cent_adv_mm = parser.getfloat(adv_section, 'from_y_cent', fallback=None)
                    if y_cent_lock_mm is not None and from_y_cent_adv_mm is not None:
                        y_pos_mm = y_cent_lock_mm + from_y_cent_adv_mm
                    print(f"🔩 {material_name}: координаты ({x_pos_mm}, {y_pos_mm}) взяты из '{config_path}'")
        except Exception as e:
            print(f"⚠️ Ошибка при чтении INI для доп. накладки: {e}")

        # Если координаты не найдены, используем значения по умолчанию
        if x_pos_mm is None:
            x_pos_mm = config.HANDLE_OFFSET_MM
            print(f"🔩 {material_name}: используется x_pos по умолчанию {x_pos_mm} мм")
        if y_pos_mm is None:
            y_pos_mm = config.HANDLE_HEIGHT_MM + config.PLATE_OFFSET_Y_MM2
            print(f"🔩 {material_name}: используется y_pos по умолчанию {y_pos_mm} мм")

        # Загрузка и константы
        model_scale_factor = config.PLATE_SCALE
        z_offset = 0.001
        print(f"🔩 {material_name}: используется файл {obj_path}")

        m = o3d.io.read_triangle_mesh(obj_path, True)
        if m.is_empty():
            print(f"Не удалось загрузить OBJ: {obj_path}")
            return None

        # --- Трансформации ---
        mn, mx = bbox(m)
        m.translate([-(mn[0] + mx[0]) / 2, 0, 0])
        m.scale(model_scale_factor, center=[0, 0, 0])

        mn2, _ = bbox(m)
        m.translate([0, 0, self.door_thickness - mn2[2] + z_offset])

        xp = x_pos_mm * self.scale if self.side == "R" else self.door_width - (x_pos_mm * self.scale)
        print(f"🔩 {material_name}: Финальная координата X = {xp:.4f} м (исходная: {x_pos_mm} мм, сторона: {self.side})")
        m.translate([xp, y_pos_mm * self.scale, 0])

        m.compute_vertex_normals()
        return m, material_name, obj_path

    def _make_hinges(self):
        """Создает петли с простым расчетом позиций"""
        if not self.params.hinge_stl or not os.path.exists(self.params.hinge_stl):
            return None

        # 1. Загружаем базовую модель петли
        base = o3d.io.read_triangle_mesh(self.params.hinge_stl)
        if base.is_empty():
            print(f"⚠️ Петля пустая: {self.params.hinge_stl}")
            return None

        # 2. Центрируем
        base.translate(-base.get_axis_aligned_bounding_box().get_center())

        # 3. Масштабируем
        base.scale(config.HINGE_SCALE, center=[0, 0, 0])

        # 4. Поворачиваем
        rx, ry, rz = config.HINGE_ROTATION_DEG
        if any((rx, ry, rz)):
            base.rotate(
                o3d.geometry.get_rotation_matrix_from_xyz(np.radians([rx, ry, rz])),
                center=[0, 0, 0]
            )


        # 6. Позиция по X (от края)
        xp = (self.door_width - config.HINGE_OFFSET_MM * self.scale
              if self.side == 'R' else config.HINGE_OFFSET_MM * self.scale)

        # 7. Функция размещения петли
        def place_hinge(y_from_bottom):
            """Размещает петлю на высоте от нижнего края"""
            h = o3d.geometry.TriangleMesh(base)

            # Переводим в центрированные координаты
            y_center = y_from_bottom

            h.translate([xp, y_center, 0.0])

            # Позиционируем по Z
            z_shift = (self.door_thickness + config.HINGE_PROTRUDE_M) - \
                      h.get_axis_aligned_bounding_box().min_bound[2]
            h.translate([0, 0, z_shift])
            h.compute_vertex_normals()
            return h

        # 8. Функция создания кольца петли
        def make_ring(y_from_bottom):
            """Создает кольцо петли"""
            ring = o3d.geometry.TriangleMesh.create_cylinder(
                radius=config.HINGE_RING_RADIUS_MM * 0.001,
                height=config.HINGE_RING_TUBE_MM * 0.001,
                resolution=48,
                split=4
            )

            ring.rotate(
                o3d.geometry.get_rotation_matrix_from_xyz(np.radians([90.0, 0.0, 0.0])),
                center=[0, 0, 0]
            )

            y_center = y_from_bottom

            top_z = self.door_thickness + config.HINGE_PROTRUDE_M + config.HINGE_RING_DZ_MM * 0.001
            ring.translate([
                xp + config.HINGE_RING_DX_MM * 0.001,
                y_center + config.HINGE_RING_DY_MM * 0.001,
                top_z,
            ])

            ring.compute_vertex_normals()
            return ring

        # 9. РАСЧЕТ ПОЗИЦИЙ ПЕТЕЛЬ
        out = []
        hinge_count = getattr(self.params, 'hinge_count', 2)

        # Отступы от краев (в метрах)
        OFFSET_FROM_BOTTOM = 0.15  # 150 мм от низа
        OFFSET_FROM_TOP = 0.15  # 150 мм от верха

        if hinge_count == 2:
            # 2 петли: нижняя и верхняя
            positions = [
                OFFSET_FROM_BOTTOM,  # Нижняя: 150 мм от низа
                self.door_height - OFFSET_FROM_TOP  # Верхняя: 150 мм от верха
            ]
            names = ["нижняя", "верхняя"]

        elif hinge_count == 3:
            # 3 петли: нижняя, средняя, верхняя
            # Средняя на 300 мм (0.3 м) ниже верхней
            DISTANCE_FROM_TOP = 0.3  # 300 мм

            positions = [
                OFFSET_FROM_BOTTOM,  # Нижняя: 150 мм от низа
                self.door_height - OFFSET_FROM_TOP - DISTANCE_FROM_TOP,  # Средняя: 300 мм ниже верхней
                self.door_height - OFFSET_FROM_TOP  # Верхняя: 150 мм от верха
            ]
            names = ["нижняя", "средняя", "верхняя"]

        # Выводим информацию
        print(f"\n📏 Петли ({hinge_count} шт.):")
        for i, (pos, name) in enumerate(zip(positions, names)):
            print(f"  {name}: {pos * 1000:.0f} мм от низа")

        # 10. Создаем петли
        for y_pos, name in zip(positions, names):
            out.append((place_hinge(y_pos), "hinge"))
            out.append((make_ring(y_pos), "ring"))

        return out

    def _make_casing(self, texture_path: Optional[str] = None):
        """Создает деревянный наличник"""
        color = (0.8, 0.8, 0.8)  # Базовый цвет, текстура его перекроет

        # Масштабируем мм в метры
        pff_m = self.pff * self.scale
        zff_m = self.zff * self.scale
        vff_m = self.vff * self.scale

        cd = 0.008
        ct = 0.010
        w, h, t = self.door_width, self.door_height, self.door_thickness

        casing_z = t + (config.WALL_Z_OFFSET_MM * 0.001 if self.inner else 0.0)
        
        # Создаем планки наличника
        
        # Определяем ширину левого (rw) и правого (cw) наличника в зависимости от стороны
        rw, cw = (zff_m, pff_m) if self.side == 'L' else (pff_m, zff_m)
        
        bars = [
            # ЛЕВАЯ
            make_casing_bar(-rw, 0, casing_z, h + vff_m, False, rw, cd, ct, color),
            # ПРАВАЯ
            make_casing_bar(w, 0, casing_z, h + vff_m, False, cw, cd, ct, color),
            # ВЕРХНЯЯ
            make_casing_bar(0, h, casing_z, w, True, vff_m, cd, ct, color),
        ]

        # Внутренние откосы
        z0 = t
        z1 = self._z_wall
        
        # Создаем геометрию откосов
        reveal_meshes = [
            make_flat_quad((0, 0, z0), (0, h, z0), (0, h, z1), (0, 0, z1), color),
            make_flat_quad((w, 0, z0), (w, h, z0), (w, h, z1), (w, 0, z1), color),
            make_flat_quad((0, h, z0), (w, h, z0), (w, h, z1), (0, h, z1), color),
        ]

        # Собираем все меши (планки и откосы) с правильным материалом и текстурой
        return [(b, "casing", texture_path) for b in bars] + [(r, "casing", texture_path) for r in reveal_meshes]