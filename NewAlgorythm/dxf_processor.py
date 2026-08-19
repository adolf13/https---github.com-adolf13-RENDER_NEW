"""
Упрощенный процессор DXF-файлов.

Поддерживает старую схему (слой ``0`` — контур, ``PIC`` — рисунок)
и схему фрезеровки: ``contour`` — контур полотна, слой с именем
фрезы (например, ``1003`` или ``D10``) — её траектория.
"""
import ezdxf
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Point:
    x: float
    y: float
    z: float = 0.0


@dataclass
class LineEntity:
    start: Point
    end: Point
    layer: str

    @classmethod
    def from_dxf_line(cls, dxf_line):
        s = dxf_line.dxf.start
        e = dxf_line.dxf.end
        return cls(
            start=Point(x=float(s.x), y=float(s.y), z=float(s.z) if hasattr(s, 'z') else 0.0),
            end=Point(x=float(e.x), y=float(e.y), z=float(e.z) if hasattr(e, 'z') else 0.0),
            layer=str(dxf_line.dxf.layer)
        )


class DXFData:
    def __init__(self):
        self.entities: Dict[str, List[LineEntity]] = {'line': []}
        self.panel_type: str = 'rect'
        self.milling_paths: Dict[str, List[LineEntity]] = {}
        self.milling_depths_mm: Dict[str, float] = {}
        self.milling_line_depths_mm: Dict[str, List[float]] = {}
        self.contour_bounds: Optional[Tuple[float, float, float, float]] = None


_CURVE_SAGITTA_MM = 0.05


def _entity_lines(entity, layer: Optional[str] = None) -> List[LineEntity]:
    """Разбить LINE, ARC и полилинию с bulge-дугами на отрезки."""
    source_layer = str(layer if layer is not None else entity.dxf.layer)
    kind = entity.dxftype()
    if kind == 'LINE':
        result = LineEntity.from_dxf_line(entity)
        result.layer = source_layer
        return [result]
    if kind == 'ARC':
        points = list(entity.flattening(_CURVE_SAGITTA_MM))
        return [
            LineEntity(
                start=Point(float(first.x), float(first.y)),
                end=Point(float(second.x), float(second.y)),
                layer=source_layer,
            )
            for first, second in zip(points, points[1:])
        ]
    if kind in {'LWPOLYLINE', 'POLYLINE'}:
        result = []
        for virtual in entity.virtual_entities():
            result.extend(_entity_lines(virtual, source_layer))
        return result
    return []


def _bounds(lines: List[LineEntity]) -> Optional[Tuple[float, float, float, float]]:
    if not lines:
        return None
    xs = [value for line in lines for value in (line.start.x, line.end.x)]
    ys = [value for line in lines for value in (line.start.y, line.end.y)]
    return min(xs), min(ys), max(xs), max(ys)


def _intersects_bounds(
    line: LineEntity,
    bounds: Tuple[float, float, float, float],
    tolerance: float = 0.1,
) -> bool:
    """Отсечь поясняющие схемы фрез за пределами полотна."""
    min_x, min_y, max_x, max_y = bounds
    line_min_x = min(line.start.x, line.end.x)
    line_max_x = max(line.start.x, line.end.x)
    line_min_y = min(line.start.y, line.end.y)
    line_max_y = max(line.start.y, line.end.y)
    return not (
        line_max_x < min_x - tolerance
        or line_min_x > max_x + tolerance
        or line_max_y < min_y - tolerance
        or line_min_y > max_y + tolerance
    )


def _dimension_depth_levels(msp) -> Dict[float, float]:
    """Return ``tip Y -> depth`` pairs from vertical dimensions in the scheme."""
    result = {}
    for dimension in msp.query('DIMENSION'):
        try:
            first = dimension.dxf.defpoint2
            second = dimension.dxf.defpoint3
            measurement = float(dimension.get_measurement())
        except (AttributeError, TypeError, ValueError):
            continue
        if measurement <= 0 or abs(float(first.x) - float(second.x)) > 0.2:
            continue
        if abs(abs(float(first.y) - float(second.y)) - measurement) > 0.2:
            continue
        result[max(float(first.y), float(second.y))] = measurement
    return result


def _infer_milling_depths(
    msp,
    scheme_paths: Dict[str, List[LineEntity]],
    tolerance: float = 0.25,
) -> Dict[str, float]:
    """Match the lowest cutter-tip point in the scheme to a dimension level."""
    levels = _dimension_depth_levels(msp)
    if not levels:
        return {}
    result = {}
    for cutter_id, lines in scheme_paths.items():
        if not lines:
            continue
        tip_y = min(
            value
            for line in lines
            for value in (line.start.y, line.end.y)
        )
        level_y, depth = min(levels.items(), key=lambda item: abs(item[0] - tip_y))
        if abs(level_y - tip_y) <= tolerance:
            result[cutter_id] = round(depth, 5)
    return result


def _connected_components(lines: List[LineEntity]) -> List[List[LineEntity]]:
    """Group path segments connected by common end points."""
    def point_key(point: Point) -> Tuple[float, float]:
        return round(point.x, 3), round(point.y, 3)

    by_point: Dict[Tuple[float, float], List[int]] = {}
    for index, line in enumerate(lines):
        for point in (line.start, line.end):
            by_point.setdefault(point_key(point), []).append(index)

    unseen = set(range(len(lines)))
    result = []
    while unseen:
        pending = [unseen.pop()]
        indices = []
        while pending:
            index = pending.pop()
            indices.append(index)
            for point in (lines[index].start, lines[index].end):
                for neighbour in by_point[point_key(point)]:
                    if neighbour in unseen:
                        unseen.remove(neighbour)
                        pending.append(neighbour)
        result.append([lines[index] for index in indices])
    return result


def _component_box(lines: List[LineEntity]) -> Tuple[float, float, float, float]:
    xs = [value for line in lines for value in (line.start.x, line.end.x)]
    ys = [value for line in lines for value in (line.start.y, line.end.y)]
    return min(xs), min(ys), max(xs), max(ys)


def _infer_milling_line_depths(
    msp,
    scheme_paths: Dict[str, List[LineEntity]],
    milling_paths: Dict[str, List[LineEntity]],
    tolerance: float = 0.25,
) -> Dict[str, List[float]]:
    """Infer repeated per-contour depths for cutters shown multiple times.

    C03 shows D10 four times from left to right.  Three tips align with the
    5 mm dimension; the raised right-hand tip is 3.5 mm higher, hence its
    engagement is 5 - 3.5 = 1.5 mm.  The same order maps to outer-to-inner
    nested contours in every panel group.
    """
    dimension_levels = _dimension_depth_levels(msp)
    result = {}
    for cutter_id, scheme_lines in scheme_paths.items():
        scheme_components = _connected_components(scheme_lines)
        if len(scheme_components) <= 1:
            continue

        scheme_records = []
        for component in scheme_components:
            min_x, min_y, max_x, _ = _component_box(component)
            direct = [
                (level_y, depth)
                for level_y, depth in dimension_levels.items()
                if abs(level_y - min_y) <= tolerance
            ]
            scheme_records.append({
                "center_x": (min_x + max_x) * 0.5,
                "tip_y": min_y,
                "depth": direct[0][1] if direct else None,
            })

        known = [record for record in scheme_records if record["depth"] is not None]
        if not known:
            continue
        for record in scheme_records:
            if record["depth"] is not None:
                continue
            reference = min(known, key=lambda item: abs(item["tip_y"] - record["tip_y"]))
            record["depth"] = reference["depth"] - (record["tip_y"] - reference["tip_y"])
        ordered_depths = [
            round(float(record["depth"]), 5)
            for record in sorted(scheme_records, key=lambda item: item["center_x"])
        ]
        if any(depth <= 0 for depth in ordered_depths):
            continue

        actual_lines = milling_paths.get(cutter_id, [])
        actual_components = _connected_components(actual_lines)
        expected_per_group = len(ordered_depths)
        groups: Dict[float, List[List[LineEntity]]] = {}
        for component in actual_components:
            min_x, min_y, max_x, max_y = _component_box(component)
            center_y = round((min_y + max_y) * 0.5, 2)
            groups.setdefault(center_y, []).append(component)
        if not groups or any(len(group) != expected_per_group for group in groups.values()):
            continue

        line_depth_by_id = {}
        for group in groups.values():
            # The left-to-right order in the section corresponds to nested
            # contours from the largest (outer) to the smallest (inner).
            ordered_components = sorted(
                group,
                key=lambda component: -(
                    (_component_box(component)[2] - _component_box(component)[0])
                    * (_component_box(component)[3] - _component_box(component)[1])
                ),
            )
            for component, depth in zip(ordered_components, ordered_depths):
                for line in component:
                    line_depth_by_id[id(line)] = depth
        result[cutter_id] = [line_depth_by_id[id(line)] for line in actual_lines]
    return result


def _classify_panel_type(panel_lines: List[LineEntity]) -> str:
    """Определяет тип панелей: rect или groove"""
    if not panel_lines:
        return 'rect'

    h = [ln for ln in panel_lines if abs(ln.end.y - ln.start.y) < 0.5]
    v = [ln for ln in panel_lines if abs(ln.end.x - ln.start.x) < 0.5]
    diag = [ln for ln in panel_lines
            if abs(ln.end.y - ln.start.y) >= 0.5 and abs(ln.end.x - ln.start.x) >= 0.5]

    if len(diag) >= 5:
        return 'groove'
    if (not h and v) or (not v and h):
        return 'groove'
    if h and v:
        ratio = max(len(h), len(v)) / max(1, min(len(h), len(v)))
        if ratio >= 4.0:
            return 'groove'
    return 'rect'


class DXFProcessor:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.doc = None
        self.msp = None

    def load(self) -> bool:
        try:
            self.doc = ezdxf.readfile(self.filepath)
            self.msp = self.doc.modelspace()
            print(f"✅ DXF загружен: {self.filepath}")
            return True
        except Exception as e:
            print(f"❌ Ошибка загрузки DXF: {e}")
            return False

    def extract_geometry(self) -> DXFData:
        data = DXFData()
        if not self.msp:
            return data

        # Извлекаем все линии
        raw = []
        for entity in self.msp:
            raw.extend(_entity_lines(entity))

        # Распределяем по слоям
        panel_lines = []
        contour_lines = []
        legacy_contour_lines = []
        for ln in raw:
            source_layer = ln.layer.strip()
            upper = source_layer.upper()
            if upper == '0':
                ln.layer = 'DOOR_LEAF'
                data.entities['line'].append(ln)
                legacy_contour_lines.append(ln)
            elif upper == 'CONTOUR':
                ln.layer = 'DOOR_LEAF'
                data.entities['line'].append(ln)
                contour_lines.append(ln)
            elif upper == 'PIC':
                ln.layer = 'PANEL'
                data.entities['line'].append(ln)
                panel_lines.append(ln)
            elif re.fullmatch(r'[A-Z]?\d+', upper):
                # Имя слоя — номер профиля фрезы.
                data.milling_paths.setdefault(upper, []).append(ln)

        data.contour_bounds = _bounds(contour_lines or legacy_contour_lines)
        if data.contour_bounds:
            scheme_paths = {
                cutter_id: [
                    line for line in lines
                    if not _intersects_bounds(line, data.contour_bounds)
                ]
                for cutter_id, lines in data.milling_paths.items()
            }
            data.milling_depths_mm = _infer_milling_depths(self.msp, scheme_paths)
            data.milling_paths = {
                cutter_id: filtered
                for cutter_id, lines in data.milling_paths.items()
                if (filtered := [
                    line for line in lines
                    if _intersects_bounds(line, data.contour_bounds)
                ])
            }
            data.milling_line_depths_mm = _infer_milling_line_depths(
                self.msp,
                scheme_paths,
                data.milling_paths,
            )
        data.panel_type = 'milling' if data.milling_paths else _classify_panel_type(panel_lines)

        print(f"📊 Извлечено линий: {len(data.entities['line'])}")
        print(f"   panel_type: {data.panel_type}")
        if data.milling_paths:
            summary = ", ".join(
                f"{cutter_id}: {len(lines)}" for cutter_id, lines in data.milling_paths.items()
            )
            print(f"   траектории фрез: {summary}")
        if data.milling_depths_mm:
            depths = ", ".join(
                f"{cutter_id}: {depth:g} мм"
                for cutter_id, depth in data.milling_depths_mm.items()
            )
            print(f"   глубины из DXF: {depths}")
        if data.milling_line_depths_mm:
            line_depths = ", ".join(
                f"{cutter_id}: "
                + "/".join(f"{depth:g}" for depth in sorted(set(depths), reverse=True))
                + " мм"
                for cutter_id, depths in data.milling_line_depths_mm.items()
            )
            print(f"   раздельные глубины траекторий: {line_depths}")
        return data
