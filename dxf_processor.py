"""
Упрощенный процессор DXF-файлов.
Ожидает: слой '0' - контур, слой 'PIC' - рисунок панели.
"""
import ezdxf
from typing import List, Dict
from collections import defaultdict
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


def _extract_polyline_lines(msp) -> List[LineEntity]:
    """Разбивает полилинии на отрезки"""
    result = []
    for pl in msp.query('POLYLINE'):
        verts = list(pl.vertices)
        for i in range(len(verts) - 1):
            a = verts[i].dxf.location
            b = verts[i + 1].dxf.location
            result.append(LineEntity(
                start=Point(float(a.x), float(a.y)),
                end=Point(float(b.x), float(b.y)),
                layer=pl.dxf.layer
            ))
    for lw in msp.query('LWPOLYLINE'):
        pts = list(lw.get_points())
        for i in range(len(pts) - 1):
            result.append(LineEntity(
                start=Point(float(pts[i][0]), float(pts[i][1])),
                end=Point(float(pts[i + 1][0]), float(pts[i + 1][1])),
                layer=lw.dxf.layer
            ))
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
        for entity in self.msp.query('LINE'):
            raw.append(LineEntity.from_dxf_line(entity))
        raw.extend(_extract_polyline_lines(self.msp))

        # Распределяем по слоям
        panel_lines = []
        for ln in raw:
            upper = ln.layer.upper()
            if upper == '0':
                ln.layer = 'DOOR_LEAF'
                data.entities['line'].append(ln)
            elif upper == 'PIC':
                ln.layer = 'PANEL'
                data.entities['line'].append(ln)
                panel_lines.append(ln)

        data.panel_type = _classify_panel_type(panel_lines)

        print(f"📊 Извлечено линий: {len(data.entities['line'])}")
        print(f"   panel_type: {data.panel_type}")
        return data
