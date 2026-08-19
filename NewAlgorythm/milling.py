"""Построение объёма, который снимает фреза при движении по DXF-траектории."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence

import ezdxf
import numpy as np
import open3d as o3d

from dxf_processor import LineEntity


_EPS_MM = 1e-5
_GEOMETRY_TIP_RADIUS_MM = 0.01


def _arc_points_with_extrema(entity, sagitta: float = 0.02):
    """Flatten an ARC while retaining its exact horizontal/vertical extrema."""
    center = entity.dxf.center
    start_angle = float(entity.dxf.start_angle) % 360.0
    end_angle = float(entity.dxf.end_angle) % 360.0
    span = (end_angle - start_angle) % 360.0

    candidates = []
    for point in entity.flattening(sagitta):
        angle = math.degrees(math.atan2(point.y - center.y, point.x - center.x)) % 360.0
        candidates.append(((angle - start_angle) % 360.0, point))
    for angle in (0.0, 90.0, 180.0, 270.0):
        relative = (angle - start_angle) % 360.0
        if relative <= span + 1e-9:
            radians = math.radians(angle)
            point = (
                float(center.x) + float(entity.dxf.radius) * math.cos(radians),
                float(center.y) + float(entity.dxf.radius) * math.sin(radians),
            )
            candidates.append((relative, point))

    result = []
    for _, point in sorted(candidates, key=lambda item: item[0]):
        xy = (float(point[0]), float(point[1]))
        if not result or math.dist(result[-1], xy) > 1e-8:
            result.append(xy)
    return result


@dataclass(frozen=True)
class CutterProfile:
    """Осевое сечение рабочей части фрезы.

    ``samples_mm`` хранит пары ``(осевое_расстояние, радиус)``:
    первая точка находится у верхней границы рабочего контура, а
    последняя — у кончика. Положение поверхности детали задаётся только
    при погружении фрезы.
    """

    cutter_id: str
    samples_mm: tuple[tuple[float, float], ...]
    source_path: str

    @property
    def depth_mm(self) -> float:
        return self.samples_mm[-1][0]

    @property
    def max_radius_mm(self) -> float:
        return max(radius for _, radius in self.samples_mm)


def truncate_profile(profile: CutterProfile, depth_mm: float | None) -> CutterProfile:
    """Return the cutter portion inside the material at the requested plunge.

    The physical cutter is positioned by its tip: the final profile point lies
    ``depth_mm`` below the panel surface.  Consequently a shallow pass uses the
    *bottom* part of the DXF profile, not the broad shoulder at its top.  Returned
    depths are remapped so that zero is the panel surface and ``depth_mm`` is the
    groove floor.

    ``depth_mm=None`` deliberately means the complete cutter profile.
    """
    if depth_mm is None:
        return profile
    depth_mm = float(depth_mm)
    if depth_mm <= 0:
        raise ValueError("Milling depth must be greater than zero")
    if depth_mm > profile.depth_mm + 1e-6:
        raise ValueError(
            f"Requested milling depth {depth_mm:g} mm exceeds cutter {profile.cutter_id} "
            f"profile depth {profile.depth_mm:g} mm"
        )

    surface_on_cutter = profile.depth_mm - depth_mm

    def radius_at(axial_position: float) -> float:
        for (first_depth, first_radius), (second_depth, second_radius) in zip(
            profile.samples_mm, profile.samples_mm[1:]
        ):
            if first_depth - _EPS_MM <= axial_position <= second_depth + _EPS_MM:
                span = second_depth - first_depth
                if span <= _EPS_MM:
                    return max(first_radius, second_radius)
                fraction = (axial_position - first_depth) / span
                return first_radius + fraction * (second_radius - first_radius)
        return profile.samples_mm[-1][1]

    result: list[tuple[float, float]] = [(0.0, radius_at(surface_on_cutter))]
    for axial_position, radius in profile.samples_mm:
        if axial_position <= surface_on_cutter + _EPS_MM:
            continue
        engaged_depth = axial_position - surface_on_cutter
        if engaged_depth >= depth_mm - _EPS_MM:
            break
        result.append((engaged_depth, radius))
    result.append((depth_mm, profile.samples_mm[-1][1]))
    return CutterProfile(profile.cutter_id, tuple(result), profile.source_path)


def _line_segments(entity) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    kind = entity.dxftype()
    if kind == 'LINE':
        start, end = entity.dxf.start, entity.dxf.end
        return [((float(start.x), float(start.y)), (float(end.x), float(end.y)))]
    if kind == 'ARC':
        points = _arc_points_with_extrema(entity)
        return list(zip(points, points[1:]))
    if kind in {'LWPOLYLINE', 'POLYLINE'}:
        result = []
        for virtual in entity.virtual_entities():
            result.extend(_line_segments(virtual))
        return result
    return []


def _cross(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    first: tuple[tuple[float, float], tuple[float, float]],
    second: tuple[tuple[float, float], tuple[float, float]],
    tolerance: float = 0.02,
) -> bool:
    """Проверка пересечения с небольшим DXF-допуском."""
    a, b = first
    c, d = second
    if (
        max(a[0], b[0]) + tolerance < min(c[0], d[0])
        or max(c[0], d[0]) + tolerance < min(a[0], b[0])
        or max(a[1], b[1]) + tolerance < min(c[1], d[1])
        or max(c[1], d[1]) + tolerance < min(a[1], b[1])
    ):
        return False

    ab = math.dist(a, b)
    cd = math.dist(c, d)
    if ab <= tolerance or cd <= tolerance:
        points_a = (a,) if ab <= tolerance else (a, b)
        points_b = (c,) if cd <= tolerance else (c, d)
        return any(math.dist(pa, pb) <= tolerance for pa in points_a for pb in points_b)

    c1, c2 = _cross(a, b, c), _cross(a, b, d)
    c3, c4 = _cross(c, d, a), _cross(c, d, b)
    scale = max(ab, cd, 1.0)
    eps = tolerance * scale
    return c1 * c2 <= eps and c3 * c4 <= eps


def _profile_axis_x(modelspace, segments) -> float:
    axis_candidates = []
    for entity in modelspace:
        layer = str(getattr(entity.dxf, 'layer', '')).casefold()
        if 'axis' not in layer and 'осев' not in layer:
            continue
        for start, end in _line_segments(entity):
            dx, dy = end[0] - start[0], end[1] - start[1]
            if abs(dy) > abs(dx):
                axis_candidates.append((math.hypot(dx, dy), (start[0] + end[0]) * 0.5))
    if axis_candidates:
        return max(axis_candidates)[1]

    xs = [point[0] for segment in segments for point in segment]
    if not xs:
        raise ValueError("В DXF фрезы не найден контур")
    return (min(xs) + max(xs)) * 0.5


def _select_profile_segments(modelspace) -> tuple[list, float]:
    contour = []
    layer_zero = []
    profile_entities = []
    for entity in modelspace:
        layer = str(getattr(entity.dxf, 'layer', '')).strip()
        target = contour if layer.casefold() == 'contour' else layer_zero if layer == '0' else None
        if target is not None:
            target.extend(_line_segments(entity))
        segments = _line_segments(entity)
        if segments:
            profile_entities.append(segments)

    if contour:
        return contour, _profile_axis_x(modelspace, contour)
    if not layer_zero:
        if len(profile_entities) != 1:
            raise ValueError(
                "В DXF фрезы не найден один замкнутый рабочий контур"
            )
        segments = profile_entities[0]
        return segments, _profile_axis_x(modelspace, segments)

    axis_x = _profile_axis_x(modelspace, layer_zero)
    selected = {
        index
        for index, (start, end) in enumerate(layer_zero)
        if min(start[0], end[0]) - 0.02 <= axis_x <= max(start[0], end[0]) + 0.02
    }
    if not selected:
        raise ValueError("Контур фрезы не пересекает её ось")

    # Подхватываем боковые сегменты профиля. Так мы игнорируем поясняющий
    # эскиз справа в исходном 1003.dxf.
    changed = True
    while changed:
        changed = False
        for index, segment in enumerate(layer_zero):
            if index in selected:
                continue
            if any(_segments_intersect(segment, layer_zero[other]) for other in selected):
                selected.add(index)
                changed = True

    return [layer_zero[index] for index in sorted(selected)], axis_x


def _cutter_id(path: str) -> str:
    cutter_id = Path(path).stem.strip().upper()
    if not re.fullmatch(r'[A-Z]?\d+', cutter_id):
        raise ValueError(f"Некорректное имя DXF фрезы: {Path(path).name}")
    return cutter_id


def load_cutter_profile(path: str) -> CutterProfile:
    """Извлечь рабочую часть профиля из DXF.

    Поверхность определяется по верхней точке максимального радиуса.
    Хвостовик, находящийся выше поверхности, в снимаемый объём не входит.
    """
    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"DXF фрезы не найден: {source}")
    document = ezdxf.readfile(source)
    segments, axis_x = _select_profile_segments(document.modelspace())
    points = [point for segment in segments for point in segment]
    radii = [abs(point[0] - axis_x) for point in points]
    max_radius = max(radii)
    surface_y = max(
        point[1]
        for point in points
        if abs(abs(point[0] - axis_x) - max_radius) <= 0.02
    )

    levels: dict[float, float] = {}
    for x, y in points:
        if y > surface_y + 0.02:
            continue
        depth = max(0.0, surface_y - y)
        key = round(depth, 5)
        levels[key] = max(levels.get(key, 0.0), abs(x - axis_x))

    samples = []
    for depth, radius in sorted(levels.items()):
        samples.append((depth, 0.0 if radius <= 1e-6 else radius))
    if not samples or samples[0][0] > 0.02 or samples[-1][0] <= 0.02:
        raise ValueError(f"Не удалось извлечь рабочий профиль из {source.name}")
    samples[0] = (0.0, samples[0][1])
    return CutterProfile(_cutter_id(str(source)), tuple(samples), str(source))


def _capsule_ring(
    start: tuple[float, float],
    end: tuple[float, float],
    radius: float,
    arc_segments: int,
) -> list[tuple[float, float]]:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        raise ValueError("Нулевой отрезок траектории фрезы")
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux

    def point(center, angle):
        return (
            center[0] + radius * (ux * math.cos(angle) + nx * math.sin(angle)),
            center[1] + radius * (uy * math.cos(angle) + ny * math.sin(angle)),
        )

    # Порядок CCW: нижняя сторона -> торец B -> верхняя сторона -> торец A.
    end_cap = [
        point(end, -math.pi / 2 + math.pi * index / arc_segments)
        for index in range(arc_segments + 1)
    ]
    start_cap = [
        point(start, math.pi / 2 + math.pi * index / arc_segments)
        for index in range(arc_segments + 1)
    ]
    return end_cap + start_cap


def make_segment_sweep_mesh(
    line: LineEntity,
    profile: CutterProfile,
    *,
    origin_mm: tuple[float, float] = (0.0, 0.0),
    surface_z_m: float = 0.0,
    scale: float = 0.001,
    arc_segments: int = 16,
    top_extension_m: float = 0.0,
) -> o3d.geometry.TriangleMesh:
    """Построить замкнутый объём прохода фрезы по одному отрезку."""
    start = (
        (line.start.x - origin_mm[0]) * scale,
        (line.start.y - origin_mm[1]) * scale,
    )
    end = (
        (line.end.x - origin_mm[0]) * scale,
        (line.end.y - origin_mm[1]) * scale,
    )
    if math.dist(start, end) <= 1e-12:
        raise ValueError("Нулевой отрезок траектории фрезы")

    vertices = []
    rings = []
    layers = []
    if top_extension_m > 0.0:
        layers.append((surface_z_m + top_extension_m, profile.samples_mm[0][1]))
    layers.extend(
        (surface_z_m - depth_mm * scale, radius_mm)
        for depth_mm, radius_mm in profile.samples_mm
    )
    for z, radius_mm in layers:
        # An ideal point tip degenerates to a line when swept along a path and
        # cannot form a manifold triangle mesh.  A 0.01 mm modelling radius is
        # far below render/manufacturing resolution but keeps Boolean topology
        # closed and stable.
        geometry_radius_mm = max(radius_mm, _GEOMETRY_TIP_RADIUS_MM)
        ring = _capsule_ring(start, end, geometry_radius_mm * scale, arc_segments)
        indices = []
        for x, y in ring:
            indices.append(len(vertices))
            vertices.append((x, y, z))
        rings.append(indices)

    triangles = []
    ring_size = len(rings[0])
    for upper, lower in zip(rings, rings[1:]):
        for index in range(ring_size):
            next_index = (index + 1) % ring_size
            triangles.append((upper[index], lower[next_index], upper[next_index]))
            triangles.append((upper[index], lower[index], lower[next_index]))

    top_center = len(vertices)
    vertices.append(((start[0] + end[0]) * 0.5, (start[1] + end[1]) * 0.5,
                     layers[0][0]))
    bottom_center = len(vertices)
    vertices.append(((start[0] + end[0]) * 0.5, (start[1] + end[1]) * 0.5,
                     layers[-1][0]))
    for index in range(ring_size):
        next_index = (index + 1) % ring_size
        triangles.append((top_center, rings[0][index], rings[0][next_index]))
        triangles.append((bottom_center, rings[-1][next_index], rings[-1][index]))

    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(np.asarray(vertices, dtype=np.float64))
    mesh.triangles = o3d.utility.Vector3iVector(np.asarray(triangles, dtype=np.int32))
    mesh.remove_duplicated_vertices()
    mesh.remove_duplicated_triangles()
    mesh.remove_degenerate_triangles()
    mesh.compute_vertex_normals()
    return mesh


def _normalise_profile_paths(
    profile_paths: str | Sequence[str] | Mapping[str, str],
) -> dict[str, CutterProfile]:
    if isinstance(profile_paths, Mapping):
        result = {}
        for cutter_id, path in profile_paths.items():
            profile = load_cutter_profile(str(path))
            result[str(cutter_id)] = profile
        return result
    if isinstance(profile_paths, (str, Path)):
        profile_paths = [str(profile_paths)]
    return {
        profile.cutter_id: profile
        for profile in (load_cutter_profile(str(path)) for path in profile_paths)
    }


def make_milling_sweep_meshes(
    milling_paths: Mapping[str, Iterable[LineEntity]],
    profile_paths: str | Sequence[str] | Mapping[str, str],
    *,
    origin_mm: tuple[float, float] = (0.0, 0.0),
    surface_z_m: float = 0.0,
    scale: float = 0.001,
    arc_segments: int = 16,
    top_extension_m: float = 0.0,
    milling_depth_mm: float | Mapping[str, float] | None = 1.5,
    milling_line_depths_mm: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, list[o3d.geometry.TriangleMesh]]:
    """Построить по одному аналитическому sweep-объёму на каждый отрезок пути.

    Объёмы соседних отрезков перекрываются. Последовательное вычитание
    этих тел даёт круглый наружный и острый внутренний угол поворота.
    """
    profiles = _normalise_profile_paths(profile_paths)
    missing = sorted(set(milling_paths) - set(profiles))
    if missing:
        raise ValueError(
            "Не передан DXF профиля для фрез: " + ", ".join(missing)
        )

    result = {}
    for cutter_id, lines in milling_paths.items():
        lines = list(lines)
        default_depth = (
            milling_depth_mm.get(cutter_id, profiles[cutter_id].depth_mm)
            if isinstance(milling_depth_mm, Mapping)
            else milling_depth_mm
        )
        line_depths = (
            list(milling_line_depths_mm[cutter_id])
            if milling_line_depths_mm and cutter_id in milling_line_depths_mm
            else None
        )
        if line_depths is not None and len(line_depths) != len(lines):
            raise ValueError(
                f"Per-line depth count for cutter {cutter_id} does not match its path count"
            )
        engaged_profiles = {}
        meshes = []
        for index, line in enumerate(lines):
            if math.hypot(line.end.x - line.start.x, line.end.y - line.start.y) <= _EPS_MM:
                continue
            depth = line_depths[index] if line_depths is not None else default_depth
            engaged_profile = engaged_profiles.setdefault(
                float(depth),
                truncate_profile(profiles[cutter_id], depth),
            )
            meshes.append(make_segment_sweep_mesh(
                line,
                engaged_profile,
                origin_mm=origin_mm,
                surface_z_m=surface_z_m,
                scale=scale,
                arc_segments=arc_segments,
                top_extension_m=top_extension_m,
            ))
        result[cutter_id] = meshes
    return result
