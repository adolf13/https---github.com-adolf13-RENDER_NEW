"""
Геометрические функции для построения двери
Взяты из оригинального final_door.py
"""
import os
import math
import numpy as np
import open3d as o3d
from typing import List, Tuple, Optional
from collections import defaultdict
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# Импортируем константы из config
from config import (
    PROFILE_Z_MM, CENTER_Z_MM,
    GROOVE_WIDTH_MM, GROOVE_RAISE_MM
)


# ═══════════════════════════════════════════════════════════════
#  ВСЕ ФУНКЦИИ ИЗ ОРИГИНАЛЬНОГО ФАЙЛА
# ═══════════════════════════════════════════════════════════════

def reconstruct_panel_rects(panel_lines_raw):
    """Восстанавливает прямоугольники из линий слоя PANEL"""

    def r2(v):
        return round(v, 1)

    h = [(x1, y1, x2, y2) for x1, y1, x2, y2 in panel_lines_raw if abs(y2 - y1) < 0.5]
    v = [(x1, y1, x2, y2) for x1, y1, x2, y2 in panel_lines_raw if abs(x2 - x1) < 0.5]
    h_by_xr = defaultdict(list)
    for x1, y1, x2, y2 in h:
        h_by_xr[(r2(min(x1, x2)), r2(max(x1, x2)))].append(r2(y1))
    v_by_yr = defaultdict(list)
    for x1, y1, x2, y2 in v:
        v_by_yr[(r2(min(y1, y2)), r2(max(y1, y2)))].append(r2(x1))
    rects = []
    for (xmin, xmax), ys in h_by_xr.items():
        for i, ymin in enumerate(sorted(set(ys))):
            for ymax in sorted(set(ys))[i + 1:]:
                vk = (ymin, ymax)
                if vk in v_by_yr:
                    xv = sorted(v_by_yr[vk])
                    if xmin in xv and xmax in xv:
                        rects.append((xmin, ymin, xmax, ymax))
    return rects


def group_rects_into_panels(rects):
    """Группирует прямоугольники в панели"""
    cy_groups = [];
    used = [False] * len(rects)
    for i, r in enumerate(rects):
        if used[i]: continue
        cy_i = (r[1] + r[3]) / 2
        group = [r];
        used[i] = True
        for j in range(i + 1, len(rects)):
            if not used[j] and abs((rects[j][1] + rects[j][3]) / 2 - cy_i) < 50:
                group.append(rects[j]);
                used[j] = True
        cy_groups.append(group)

    final_groups = []
    for cy_group in cy_groups:
        col_map = defaultdict(list)
        for r in cy_group:
            cx = (r[0] + r[2]) / 2
            matched = None
            for key_cx in col_map:
                if abs(key_cx - cx) < 100:
                    matched = key_cx;
                    break
            col_map[matched if matched is not None else cx].append(r)
        for col_rects in col_map.values():
            col_rects.sort(key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
            final_groups.append(col_rects)
    return final_groups


def make_raised_panel_meshes(groups, scale, door_thickness, min_x_mm, min_y_mm,
                             door_width, door_height):
    """Создает меши для рельефных панелей"""

    def to_m(x_mm, y_mm):
        return (x_mm - min_x_mm) * scale, (y_mm - min_y_mm) * scale

    def z_m(z_mm):
        return door_thickness + z_mm * 0.001

    def uv(x, y):
        return x / door_width, y / door_height

    def _mesh_with_uv(verts_np, tris_np):
        m = o3d.geometry.TriangleMesh()
        m.vertices = o3d.utility.Vector3dVector(verts_np)
        m.triangles = o3d.utility.Vector3iVector(tris_np)
        uvs = []
        for tri in tris_np:
            for vi in tri:
                vx, vy = verts_np[vi][0], verts_np[vi][1]
                uvs.append(uv(vx, vy))
        m.triangle_uvs = o3d.utility.Vector2dVector(np.array(uvs, dtype=np.float64))
        m.compute_vertex_normals()
        return m

    all_meshes = []
    for group in groups:
        n = len(group)
        z_levels = [z_m(PROFILE_Z_MM[k] if k < len(PROFILE_Z_MM) else -18.0) for k in range(n)]
        z_center = z_m(CENTER_Z_MM)

        for k in range(n - 1):
            outer = group[k];
            inner = group[k + 1]
            z_out = z_levels[k];
            z_in = z_levels[k + 1]
            ox0, oy0 = to_m(outer[0], outer[1])
            ox1, oy1 = to_m(outer[2], outer[3])
            ix0, iy0 = to_m(inner[0], inner[1])
            ix1, iy1 = to_m(inner[2], inner[3])
            b = 0.005
            verts = np.array([
                [ox0, oy0, z_out], [ox1, oy0, z_out], [ox1, oy1, z_out], [ox0, oy1, z_out],
                [ix0 - b, iy0 - b, z_out], [ix1 + b, iy0 - b, z_out], [ix1 + b, iy1 + b, z_out],
                [ix0 - b, iy1 + b, z_out],
                [ix0, iy0, z_in], [ix1, iy0, z_in], [ix1, iy1, z_in], [ix0, iy1, z_in],
            ], dtype=np.float64)
            tris = np.array([
                [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
                [4, 5, 9], [4, 9, 8], [5, 6, 10], [5, 10, 9], [6, 7, 11], [6, 11, 10], [7, 4, 8], [7, 8, 11],
            ], dtype=np.int32)
            all_meshes.append(_mesh_with_uv(verts, tris))

        inn = group[-1]
        ix0, iy0 = to_m(inn[0], inn[1])
        ix1, iy1 = to_m(inn[2], inn[3])
        cv = np.array([
            [ix0, iy0, z_center], [ix1, iy0, z_center], [ix1, iy1, z_center], [ix0, iy1, z_center],
        ], dtype=np.float64)
        all_meshes.append(_mesh_with_uv(cv, np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)))

        if abs(z_center - z_levels[-1]) > 1e-5:
            zt = z_levels[-1]
            wv = np.array([
                [ix0, iy0, zt], [ix1, iy0, zt], [ix1, iy1, zt], [ix0, iy1, zt],
                [ix0, iy0, z_center], [ix1, iy0, z_center], [ix1, iy1, z_center], [ix0, iy1, z_center],
            ], dtype=np.float64)
            wt = np.array([
                [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2], [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0],
            ], dtype=np.int32)
            all_meshes.append(_mesh_with_uv(wv, wt))

    return all_meshes


def make_groove_meshes(panel_lines_raw, scale, door_thickness, min_x_mm, min_y_mm,
                       door_width, door_height,
                       groove_width_mm=GROOVE_WIDTH_MM, raise_mm=GROOVE_RAISE_MM):
    """Создает меши для groove-валиков"""

    def to_m(x_mm, y_mm):
        return (x_mm - min_x_mm) * scale, (y_mm - min_y_mm) * scale

    half_w = (groove_width_mm * 0.5) * scale
    z0 = door_thickness
    z1 = door_thickness + raise_mm * 0.001

    def uv(xm, ym):
        return [xm / door_width, ym / door_height]

    all_meshes = []
    for (x1, y1, x2, y2) in panel_lines_raw:
        ax, ay = to_m(x1, y1)
        bx, by = to_m(x2, y2)
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 1e-6:
            continue
        ux, uy = dx / L, dy / L
        px, py = -uy, ux

        c0 = (ax + px * half_w, ay + py * half_w)
        c1 = (ax - px * half_w, ay - py * half_w)
        c2 = (bx - px * half_w, by - py * half_w)
        c3 = (bx + px * half_w, by + py * half_w)

        verts = np.array([
            [c0[0], c0[1], z0], [c1[0], c1[1], z0],
            [c2[0], c2[1], z0], [c3[0], c3[1], z0],
            [c0[0], c0[1], z1], [c1[0], c1[1], z1],
            [c2[0], c2[1], z1], [c3[0], c3[1], z1],
        ], dtype=np.float64)

        tris = np.array([
            [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
            [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6],
            [3, 0, 4], [3, 4, 7],
        ], dtype=np.int32)

        m = o3d.geometry.TriangleMesh()
        m.vertices = o3d.utility.Vector3dVector(verts)
        m.triangles = o3d.utility.Vector3iVector(tris)
        uvs = []
        for tri in tris:
            for vi in tri:
                uvs.append(uv(verts[vi][0], verts[vi][1]))
        m.triangle_uvs = o3d.utility.Vector2dVector(np.array(uvs, dtype=np.float64))
        m.compute_vertex_normals()
        all_meshes.append(m)

    return all_meshes


def make_door_front_with_holes(door_width, door_height, door_thickness,
                               groups, scale, min_x_mm, min_y_mm, texture_path):
    """Создает переднюю грань с отверстиями под панели"""
    t = door_thickness;
    W = door_width;
    H = door_height

    def to_m(x_mm, y_mm):
        return (x_mm - min_x_mm) * scale, (y_mm - min_y_mm) * scale

    outer_m = []
    for group in groups:
        r = group[0]
        x0, y0 = to_m(r[0], r[1]);
        x1, y1 = to_m(r[2], r[3])
        outer_m.append((x0, y0, x1, y1))

    def in_panel(cx, cy):
        for px0, py0, px1, py1 in outer_m:
            if px0 <= cx <= px1 and py0 <= cy <= py1: return True
        return False

    all_xs = sorted(set([0.0, W] + [v for r in outer_m for v in [r[0], r[2]]]))
    all_ys = sorted(set([0.0, H] + [v for r in outer_m for v in [r[1], r[3]]]))
    verts_list = [];
    tris_list = [];
    uv_list = [];
    vi = 0
    for xi in range(len(all_xs) - 1):
        for yi in range(len(all_ys) - 1):
            x0c, x1c = all_xs[xi], all_xs[xi + 1]
            y0c, y1c = all_ys[yi], all_ys[yi + 1]
            if in_panel((x0c + x1c) / 2, (y0c + y1c) / 2): continue
            verts_list += [[x0c, y0c, t], [x1c, y0c, t], [x1c, y1c, t], [x0c, y1c, t]]
            tris_list += [[vi, vi + 1, vi + 2], [vi, vi + 2, vi + 3]]
            uv_list += [
                [x0c / W, y0c / H], [x1c / W, y0c / H], [x1c / W, y1c / H],
                [x0c / W, y0c / H], [x1c / W, y1c / H], [x0c / W, y1c / H],
            ]
            vi += 4
    if not verts_list: return None
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(np.array(verts_list, dtype=np.float64))
    mesh.triangles = o3d.utility.Vector3iVector(np.array(tris_list, dtype=np.int32))
    mesh.triangle_uvs = o3d.utility.Vector2dVector(np.array(uv_list, dtype=np.float64))
    mesh.compute_vertex_normals()
    return mesh


def make_door_front_plain(door_width, door_height, door_thickness, texture_path):
    """Создает сплошную переднюю грань"""
    W = door_width;
    H = door_height;
    t = door_thickness
    verts = np.array([[0, 0, t], [W, 0, t], [W, H, t], [0, H, t]], dtype=np.float64)
    tris = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    uv_list = [[0, 0], [1, 0], [1, 1], [0, 0], [1, 1], [0, 1]]
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(verts)
    mesh.triangles = o3d.utility.Vector3iVector(tris)
    mesh.triangle_uvs = o3d.utility.Vector2dVector(np.array(uv_list, dtype=np.float64))
    mesh.compute_vertex_normals()
    return mesh


def make_floor(door_width, door_height, door_thickness,
               floor_width_m=6.0, floor_depth_m=4.0,
               floor_texture_path=None, tile_u=4.0, tile_v=4.0):
    """Создает пол"""
    cx = door_width / 2
    x0 = cx - floor_width_m / 2;
    x1 = cx + floor_width_m / 2
    z0 = 0.0;
    z1 = floor_depth_m
    y = -0.001
    verts = np.array([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]], dtype=np.float64)
    tris = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    uv_list = [[0.0, 0.0], [tile_u, 0.0], [tile_u, tile_v], [0.0, 0.0], [tile_u, tile_v], [0.0, tile_v]]
    m = o3d.geometry.TriangleMesh()
    m.vertices = o3d.utility.Vector3dVector(verts)
    m.triangles = o3d.utility.Vector3iVector(tris)
    m.triangle_uvs = o3d.utility.Vector2dVector(np.array(uv_list, dtype=np.float64))
    m.paint_uniform_color([0.75, 0.65, 0.55])
    m.compute_vertex_normals()
    return m


def make_wall(door_width, door_height, door_thickness,
              wall_width_m=6.0, wall_height_m=3.0,
              wall_texture_path=None, tile_u=3.0, tile_v=2.0, z=0.023):
    """Создает стену"""
    cx = door_width / 2
    x0 = cx - wall_width_m / 2
    x1 = cx + wall_width_m / 2
    H = wall_height_m
    dx0, dx1 = 0.0, door_width
    dy0, dy1 = 0.0, door_height

    def uv(x, y):
        return [(x - x0) * tile_u / wall_width_m, y * tile_v / H]

    verts = np.array([
        [x0, 0, z], [x1, 0, z], [x1, H, z], [x0, H, z],
        [dx0, dy0, z], [dx1, dy0, z], [dx1, dy1, z], [dx0, dy1, z],
        [x0, dy1, z], [x1, dy1, z], [dx0, H, z], [dx1, H, z],
    ], dtype=np.float64)

    uvs = np.array([uv(x, y) for x, y, _ in verts])
    tris = np.array([
        [0, 1, 5], [0, 5, 4], [0, 4, 7], [0, 7, 8],
        [5, 1, 9], [5, 9, 6], [8, 7, 10], [8, 10, 3],
        [6, 9, 2], [6, 2, 11], [7, 6, 11], [7, 11, 10],
    ], dtype=np.int32)

    uv_list = []
    for tri in tris:
        for vi in tri:
            uv_list.append(uvs[vi])

    m = o3d.geometry.TriangleMesh()
    m.vertices = o3d.utility.Vector3dVector(verts)
    m.triangles = o3d.utility.Vector3iVector(tris)
    m.triangle_uvs = o3d.utility.Vector2dVector(np.array(uv_list, dtype=np.float64))
    m.paint_uniform_color([0.88, 0.84, 0.78])
    m.compute_vertex_normals()
    return m


def make_casing_bar(x0, y0, z0, length, along_x, cw, cd, ct, color):
    """Создает планку наличника"""
    EPS = 0.0005
    if along_x:
        verts = np.array([
            [x0, y0, z0 - ct + EPS], [x0 + length, y0, z0 - ct + EPS],
            [x0 + length, y0 + cw, z0 - ct + EPS], [x0, y0 + cw, z0 - ct + EPS],
            [x0, y0, z0 + cd], [x0 + length, y0, z0 + cd],
            [x0 + length, y0 + cw, z0 + cd], [x0, y0 + cw, z0 + cd],
        ], dtype=np.float64)
    else:
        verts = np.array([
            [x0, y0, z0 - ct + EPS], [x0 + cw, y0, z0 - ct + EPS],
            [x0 + cw, y0 + length, z0 - ct + EPS], [x0, y0 + length, z0 - ct + EPS],
            [x0, y0, z0 + cd], [x0 + cw, y0, z0 + cd],
            [x0 + cw, y0 + length, z0 + cd], [x0, y0 + length, z0 + cd],
        ], dtype=np.float64)
    tris = np.array([
        [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
        [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
    ], dtype=np.int32)
    m = o3d.geometry.TriangleMesh()
    m.vertices = o3d.utility.Vector3dVector(verts)
    m.triangles = o3d.utility.Vector3iVector(tris)
    m.paint_uniform_color(list(color))

    # --- Добавлено: Ручная генерация UV-координат ---
    # Создаем UV-координаты для каждой из 6 граней параллелепипеда
    uvs = np.array([
        [0, 0], [1, 0], [1, 1], [0, 1], # back
        [0, 0], [1, 0], [1, 1], [0, 1], # front
    ])
    m.triangle_uvs = o3d.utility.Vector2dVector(np.array([
        uvs[0], uvs[2], uvs[1], uvs[0], uvs[3], uvs[2], # back
        uvs[4], uvs[5], uvs[6], uvs[4], uvs[6], uvs[7], # front
        uvs[0], uvs[1], uvs[5], uvs[0], uvs[5], uvs[4], # bottom
        uvs[1], uvs[2], uvs[6], uvs[1], uvs[6], uvs[5], # right
        uvs[2], uvs[3], uvs[7], uvs[2], uvs[7], uvs[6], # top
        uvs[3], uvs[0], uvs[4], uvs[3], uvs[4], uvs[7], # left
    ], dtype=np.float64))

    m.compute_vertex_normals()
    return m


def make_flat_quad(p0, p1, p2, p3, color):
    """Создает двусторонний плоский прямоугольник"""
    verts = np.array([p0, p1, p2, p3, p0, p1, p2, p3], dtype=np.float64)
    
    # --- Добавлено: Ручная генерация UV-координат ---
    uvs = np.array([
        [0, 0], [1, 0], [1, 1], [0, 1] 
    ])

    tris = np.array([
        [0, 1, 2], [0, 2, 3],
        [4, 6, 5], [4, 7, 6],
    ], dtype=np.int32)

    m = o3d.geometry.TriangleMesh()
    m.vertices = o3d.utility.Vector3dVector(verts)
    m.triangles = o3d.utility.Vector3iVector(tris)
    m.triangle_uvs = o3d.utility.Vector2dVector(np.array([
        uvs[0], uvs[1], uvs[2], uvs[0], uvs[2], uvs[3], # front
        uvs[0], uvs[2], uvs[1], uvs[0], uvs[3], uvs[2], # back
    ], dtype=np.float64))
    m.paint_uniform_color(list(color))
    m.compute_vertex_normals()
    return m

def make_metal_frame(frame_stl_path, door_width, door_height, door_thickness,
                     frame_scale: float, texture_path: Optional[str],
                     frame_rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                     extra_y_180=False, z_offset=0.0):
    """Загружает и позиционирует STL коробку"""
    if not frame_stl_path or not os.path.exists(frame_stl_path):
        print(f"⚠ STL коробки не найден: {frame_stl_path}")
        return None

    m = o3d.io.read_triangle_mesh(frame_stl_path)
    if m.is_empty():
        print(f"⚠ STL коробки пустой")
        return None

    bb = m.get_axis_aligned_bounding_box()
    center = (np.array(bb.min_bound) + np.array(bb.max_bound)) / 2.0
    m.translate(-center)

    R = o3d.geometry.get_rotation_matrix_from_xyz(np.radians([-90.0, 180.0, 90.0]))
    m.rotate(R, center=[0, 0, 0])

    rx, ry, rz = frame_rotation_deg
    if abs(rx) > 0.01 or abs(ry) > 0.01 or abs(rz) > 0.01:
        R2 = o3d.geometry.get_rotation_matrix_from_xyz(np.radians([rx, ry, rz]))
        m.rotate(R2, center=[0, 0, 0])

    m.scale(frame_scale, center=[0, 0, 0])

    bb2 = m.get_axis_aligned_bounding_box()
    mn2 = np.array(bb2.min_bound);
    mx2 = np.array(bb2.max_bound)
    tx = door_width / 2.0 - (mn2[0] + mx2[0]) / 2.0
    ty = -mn2[1] - 0.04
    tz = -mx2[2] + 0.045
    m.translate([tx, ty, tz])

    if extra_y_180:
        c = m.get_axis_aligned_bounding_box().get_center()
        Rflip = o3d.geometry.get_rotation_matrix_from_xyz(np.radians([0.0, 180.0, 0.0]))
        m.rotate(Rflip, center=c)

    if abs(z_offset) > 1e-9:
        m.translate([0.0, 0.0, z_offset])

    m.paint_uniform_color([0.8, 0.8, 0.8])  # Базовый цвет, будет перекрыт текстурой
    m.compute_vertex_normals()
    return m


# ═══════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════

def load_stl(path):
    """
    Загружает STL файл.
    Для Windows с кириллицей создает копию во временной папке.
    """
    import tempfile
    import shutil
    import time

    if not path or not os.path.exists(path):
        print(f"⚠ STL не найден: {path}")
        return None

    # Нормализуем путь
    path = os.path.normpath(path)

    # Пробуем загрузить напрямую
    try:
        m = o3d.io.read_triangle_mesh(path)
        if not m.is_empty():
            return m
    except:
        pass

    # Создаем временную копию с латинским именем
    tmp_name = None
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as tmp:
            tmp_name = tmp.name

        # Копируем содержимое
        shutil.copy2(path, tmp_name)

        # Загружаем из временного файла
        m = o3d.io.read_triangle_mesh(tmp_name)

        if m.is_empty():
            print(f"⚠ STL пустой: {path}")
            return None

        # Удаляем временный файл с задержкой
        def delayed_delete():
            import time
            time.sleep(0.5)
            try:
                os.unlink(tmp_name)
            except:
                pass

        import threading
        threading.Thread(target=delayed_delete, daemon=True).start()

        return m

    except Exception as e:
        print(f"⚠ Ошибка загрузки STL: {e}")
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except:
                pass
        return None


def rot(mesh, rx, ry, rz):
    """Поворачивает меш"""
    R = o3d.geometry.get_rotation_matrix_from_xyz(np.radians([rx, ry, rz]))
    mesh.rotate(R, center=[0, 0, 0])
    return mesh


def bbox(mesh):
    """Возвращает bounding box меша"""
    b = mesh.get_axis_aligned_bounding_box()
    return b.min_bound, b.max_bound
