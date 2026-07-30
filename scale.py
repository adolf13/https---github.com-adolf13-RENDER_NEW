"""
Модуль для масштабирования DXF файлов панелей
Специфическая обработка:
- Слой "0" содержит контур панели (прямоугольник)
- Слой "Pic" содержит траектории фрез (линии, дуги, окружности, полилинии)
"""

import ezdxf
import logging
import shutil
from pathlib import Path
from typing import Union, Optional, Tuple, List
from ezdxf.math import Vec3, Matrix44

logger = logging.getLogger(__name__)


class PanelScaler:
    """
    Класс для масштабирования DXF файлов панелей
    """
    
    # Базовые размеры (исходные размеры ПОЛОТНА в DXF)
    BASE_PANEL_WIDTH = 900.0
    BASE_PANEL_HEIGHT = 2000.0
    
    # Зазор между проемом и полотном
    CLEARANCE = 50.0  # 50 мм с каждой стороны (или 25+25)
    
    def __init__(self, source_path: Union[str, Path], output_dir: Union[str, Path]):
        """
        Инициализация масштабатора
        
        Args:
            source_path: путь к исходному DXF файлу
            output_dir: директория для сохранения масштабированного файла
        """
        self.source_path = Path(source_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Слои для обработки
        self.contour_layer = "0"  # Контур панели
        self.pic_layer = "Pic"    # Траектории фрез
    
    def scale_panel(
        self, 
        target_width: float,
        target_height: float,
        preserve_ratio: bool = False,
        output_filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Масштабирует DXF файл панели до заданных размеров полотна
        
        Args:
            target_width: целевая ширина ПОЛОТНА (например, 830)
            target_height: целевая высота ПОЛОТНА (например, 2000)
            preserve_ratio: если True, сохранять пропорции
            output_filename: имя выходного файла
        
        Returns:
            Path: путь к сохраненному файлу или None при ошибке
        """
        if not self.source_path.exists():
            logger.error(f"Исходный файл не найден: {self.source_path}")
            return None
        
        if target_width <= 0 or target_height <= 0:
            logger.error(f"Размеры должны быть положительными: {target_width}x{target_height}")
            return None
        
        # Расчет масштабов ОТНОСИТЕЛЬНО БАЗОВОГО ПОЛОТНА
        x_scale = target_width / self.BASE_PANEL_WIDTH
        y_scale = target_height / self.BASE_PANEL_HEIGHT
        
        logger.info(f"Исходное полотно: {self.BASE_PANEL_WIDTH}x{self.BASE_PANEL_HEIGHT}")
        logger.info(f"Целевое полотно: {target_width}x{target_height}")
        logger.info(f"Масштабы: x={x_scale:.6f}, y={y_scale:.6f}")
        
        if preserve_ratio:
            scale = min(x_scale, y_scale)
            x_scale = y_scale = scale
            logger.info(f"Сохранение пропорций, масштаб: {scale:.6f}")
        
        # Генерируем имя выходного файла
        if output_filename is None:
            stem = self.source_path.stem
            if preserve_ratio:
                output_filename = f"{stem}_{target_width:.0f}x{target_height:.0f}_prop.dxf"
            else:
                output_filename = f"{stem}_{target_width:.0f}x{target_height:.0f}.dxf"
        
        output_path = self.output_dir / output_filename
        
        try:
            # Копируем исходный файл
            shutil.copy2(self.source_path, output_path)
            
            # Открываем скопированный файл
            doc = ezdxf.readfile(str(output_path))
            msp = doc.modelspace()
            
            # Масштабируем сущности
            scaled_count = self._scale_entities(msp, x_scale, y_scale)
            logger.info(f"Масштабировано {scaled_count} сущностей")
            
            doc.saveas(str(output_path))
            logger.info(f"Файл сохранен: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Ошибка при масштабировании: {e}")
            if output_path.exists():
                output_path.unlink()
            return None
    
    # ========== НОВЫЙ МЕТОД ДЛЯ РАБОТЫ С ПРОЕМОМ ==========
    
    def scale_panel_by_opening(
        self,
        opening_width: float,
        opening_height: float,
        preserve_ratio: bool = False,
        output_filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Масштабирует панель на основе размеров ПРОЕМА
        
        Формула: Полотно = Проем - 50 мм (по ширине и высоте)
        
        Args:
            opening_width: ширина проема (например, 880)
            opening_height: высота проема (например, 2050)
            preserve_ratio: сохранять пропорции рисунка
            output_filename: имя выходного файла
        
        Returns:
            Path: путь к сохраненному файлу
        
        Пример:
            opening_width=880, opening_height=2050
            → panel_width=830, panel_height=2000
            → масштаб: 830/900, 2000/2000
        """
        # Расчет размеров полотна из проема
        panel_width = opening_width - self.CLEARANCE
        panel_height = opening_height - self.CLEARANCE
        
        if panel_width <= 0 or panel_height <= 0:
            logger.error(f"Некорректные размеры проема: {opening_width}x{opening_height}")
            return None
        
        logger.info(f"Проем: {opening_width}x{opening_height} → Полотно: {panel_width}x{panel_height}")
        
        # Генерируем имя файла
        if output_filename is None:
            stem = self.source_path.stem
            output_filename = f"{stem}_opening_{opening_width:.0f}x{opening_height:.0f}.dxf"
        
        # Используем существующий метод масштабирования
        return self.scale_panel(panel_width, panel_height, preserve_ratio, output_filename)
    
    # ========== МЕТОД ДЛЯ РАБОТЫ С КОЭФФИЦИЕНТОМ НАПРЯМУЮ ==========
    
    def scale_panel_with_coefficient(
        self,
        coeff_x: float,
        coeff_y: float,
        preserve_ratio: bool = False,
        output_filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Масштабирует панель с заданными коэффициентами относительно исходного полотна
        
        Args:
            coeff_x: коэффициент по ширине (например, 830/900 = 0.922222)
            coeff_y: коэффициент по высоте (например, 2000/2000 = 1.0)
            preserve_ratio: сохранять пропорции
            output_filename: имя выходного файла
        
        Returns:
            Path: путь к сохраненному файлу
        """
        target_width = self.BASE_PANEL_WIDTH * coeff_x
        target_height = self.BASE_PANEL_HEIGHT * coeff_y
        
        logger.info(f"Коэффициенты: x={coeff_x:.6f}, y={coeff_y:.6f}")
        logger.info(f"Целевые размеры: {target_width:.1f}x{target_height:.1f}")
        
        return self.scale_panel(target_width, target_height, preserve_ratio, output_filename)
    
    # ========== ОСТАЛЬНЫЕ МЕТОДЫ (БЕЗ ИЗМЕНЕНИЙ) ==========
    
    def scale_panel_with_custom_base(
        self,
        base_width: float,
        base_height: float,
        target_width: float,
        target_height: float,
        preserve_ratio: bool = False,
        output_filename: Optional[str] = None
    ) -> Optional[Path]:
        """Масштабирует с пользовательскими базовыми размерами"""
        original_base_width = self.BASE_PANEL_WIDTH
        original_base_height = self.BASE_PANEL_HEIGHT
        
        self.BASE_PANEL_WIDTH = base_width
        self.BASE_PANEL_HEIGHT = base_height
        
        try:
            result = self.scale_panel(target_width, target_height, preserve_ratio, output_filename)
        finally:
            self.BASE_PANEL_WIDTH = original_base_width
            self.BASE_PANEL_HEIGHT = original_base_height
        
        return result
    
    def _scale_entities(self, msp, x_scale: float, y_scale: float) -> int:
        """Масштабирует сущности в пространстве модели"""
        entities = list(msp)
        scaled_count = 0
        
        for entity in entities:
            layer = entity.dxf.get('layer', '')
            
            if layer == self.contour_layer or layer == self.pic_layer:
                try:
                    self._scale_single_entity(entity, x_scale, y_scale)
                    scaled_count += 1
                except Exception as e:
                    logger.warning(f"Ошибка масштабирования {entity.dxftype()}: {e}")
        
        return scaled_count
    
    def _scale_single_entity(self, entity, x_scale: float, y_scale: float):
        """Масштабирует одну сущность"""
        etype = entity.dxftype()
        
        # LINE
        if etype == 'LINE':
            start = entity.dxf.start
            end = entity.dxf.end
            entity.dxf.start = (start.x * x_scale, start.y * y_scale, start.z)
            entity.dxf.end = (end.x * x_scale, end.y * y_scale, end.z)
        
        # CIRCLE
        elif etype == 'CIRCLE':
            center = entity.dxf.center
            radius = entity.dxf.radius
            
            if abs(x_scale - y_scale) > 1e-10:
                # Разные масштабы → превращаем в эллипс
                doc = entity.doc
                msp = doc.modelspace()
                color = entity.dxf.get('color', 7)
                layer = entity.dxf.get('layer', '0')
                
                ellipse = msp.add_ellipse(
                    center=(center.x * x_scale, center.y * y_scale, center.z),
                    major_axis=(radius * abs(x_scale), 0, 0),
                    ratio=abs(y_scale / x_scale) if x_scale != 0 else 1,
                    dxfattribs={'color': color, 'layer': layer}
                )
                msp.delete_entity(entity)
            else:
                entity.dxf.center = (center.x * x_scale, center.y * y_scale, center.z)
                entity.dxf.radius = radius * x_scale
        
        # ARC
        elif etype == 'ARC':
            center = entity.dxf.center
            radius = entity.dxf.radius
            entity.dxf.center = (center.x * x_scale, center.y * y_scale, center.z)
            avg_scale = (abs(x_scale) + abs(y_scale)) / 2
            entity.dxf.radius = radius * avg_scale
        
        # LWPOLYLINE
        elif etype == 'LWPOLYLINE':
            points = []
            for point in entity.get_points():  # type: ignore
                x, y = point[0], point[1]
                if len(point) > 4:
                    points.append((x * x_scale, y * y_scale, point[2], point[3], point[4]))
                elif len(point) > 2:
                    points.append((x * x_scale, y * y_scale, point[2]))
                else:
                    points.append((x * x_scale, y * y_scale))
            entity.set_points(points)  # type: ignore
        
        # POLYLINE
        elif etype == 'POLYLINE':
            for vertex in entity.vertices:  # type: ignore
                location = vertex.dxf.location
                vertex.dxf.location = (location.x * x_scale, location.y * y_scale, location.z)
        
        # INSERT
        elif etype == 'INSERT':
            insert = entity.dxf.insert
            entity.dxf.insert = (insert.x * x_scale, insert.y * y_scale, insert.z)
            
            if hasattr(entity, 'attribs'):
                for attrib in entity.attribs:  # type: ignore
                    if hasattr(attrib.dxf, 'insert'):
                        ins = attrib.dxf.insert
                        attrib.dxf.insert = (ins.x * x_scale, ins.y * y_scale, ins.z)
                    if hasattr(attrib.dxf, 'height'):
                        avg_scale = (abs(x_scale) + abs(y_scale)) / 2
                        attrib.dxf.height *= avg_scale
        
        # Для остальных типов используем матрицу
        else:
            matrix = Matrix44.scale(x_scale, y_scale, 1.0)
            entity.transform(matrix)
    
    def get_panel_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """Получает границы контура панели (слой '0')"""
        # ... (оставьте как есть)
        pass
    
    def _get_entity_points(self, entity) -> List[Tuple[float, float]]:
        """Получает все точки из сущности"""
        # ... (оставьте как есть)
        pass


# ========== УПРОЩЕННЫЕ ФУНКЦИИ ==========

def scale_panel_by_opening(
    source_path: Union[str, Path],
    output_dir: Union[str, Path],
    opening_width: float,
    opening_height: float,
    preserve_ratio: bool = False,
    output_filename: Optional[str] = None
) -> Optional[Path]:
    """
    Масштабирует DXF панели по размерам проема
    
    Пример:
        scale_panel_by_opening("panel.dxf", "output/", 880, 2050)
        → полотно станет 830x2000
    """
    scaler = PanelScaler(source_path, output_dir)
    return scaler.scale_panel_by_opening(opening_width, opening_height, preserve_ratio, output_filename)


def scale_panel_with_coeff(
    source_path: Union[str, Path],
    output_dir: Union[str, Path],
    coeff_x: float,
    coeff_y: float,
    preserve_ratio: bool = False,
    output_filename: Optional[str] = None
) -> Optional[Path]:
    """
    Масштабирует DXF панели с заданными коэффициентами
    
    Пример:
        # Для проема 880 (полотно 830)
        scale_panel_with_coeff("panel.dxf", "output/", 830/900, 1.0)
    """
    scaler = PanelScaler(source_path, output_dir)
    return scaler.scale_panel_with_coefficient(coeff_x, coeff_y, preserve_ratio, output_filename)


# ========== ПРИМЕР ИСПОЛЬЗОВАНИЯ ==========

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    script_dir = Path(__file__).parent
    
    # === ВАРИАНТ 1: Масштабирование по размеру ПРОЕМА ===
    # Проем 880x2050 → полотно 830x2000
    result = scale_panel_by_opening(
        source_path=script_dir / "D-L8.dxf",
        output_dir=script_dir / "temp/",
        opening_width=880,
        opening_height=2050
    )
    print(f"Результат: {result}")
    
    # === ВАРИАНТ 2: Масштабирование с явным КОЭФФИЦИЕНТОМ ===
    # Для проема 880: 830/900 = 0.922222
    result2 = scale_panel_with_coeff(
        source_path=script_dir / "D-L8.dxf",
        output_dir=script_dir / "temp/",
        coeff_x=830 / 900,  # 0.922222...
        coeff_y=2000 / 2000  # 1.0
    )
    print(f"Результат: {result2}")
    
    # === ВАРИАНТ 3: Для другого проема, например 1050 ===
    # Проем 1050x2150 → полотно 1000x2100
    result3 = scale_panel_by_opening(
        source_path=script_dir / "D-L8.dxf",
        output_dir=script_dir / "temp/",
        opening_width=1050,
        opening_height=2150
    )
    print(f"Результат: {result3}")