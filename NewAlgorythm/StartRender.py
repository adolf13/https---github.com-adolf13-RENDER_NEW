"""Преобразование тела договора WEB_NST в параметры RENDER_NEW.

WEB_NST передаёт словарь ``data`` без преобразований. Дополнительно запрос
может содержать текстуры сцены и DXF-профили фрез. Вся расшифровка
заказа, включая комплект OBJ+MTL фурнитуры, находится в этом модуле.
"""

from __future__ import annotations

import argparse
import datetime
import hmac
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))


def _configure_output_encoding() -> None:
    """Не позволять служебным Unicode-сообщениям ронять процесс Windows."""
    if os.name != "nt":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="backslashreplace")


_configure_output_encoding()

from main import DoorParams, generate_door


SCENE_DEFAULTS = {
    "wall_texture_path": "decor/wall3.jpg",
    "floor_texture_path": "decor/floor.jpg",
    "wall_texture_path_inner": "decor/wall.jpg",
    "floor_texture_path_inner": "decor/floor.jpg",
}
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
_REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _required_text(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ValueError(f"В данных договора не заполнено поле «{key}»")
    return value


def _number(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"В данных договора некорректно заполнено поле «{key}»") from exc


def _flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() not in {"", "0", "false", "нет", "none"}
    return bool(value)


def _optional_finish(value: Any) -> str | None:
    text = str(value or "").strip()
    normalized = text.casefold().strip(" -")
    if (
        not text
        or normalized in {"выбрать", "no_data", "none"}
        or re.fullmatch(r"\d+(?:[.,]\d+)?", text)
    ):
        return None
    return text


def _directory_by_name(root: Path, name: str, field_name: str) -> Path:
    normalized = name.strip().casefold().replace("ё", "е")
    for directory in root.iterdir():
        candidate = directory.name.casefold().replace("ё", "е")
        if directory.is_dir() and candidate == normalized:
            return directory
    raise ValueError(f"Для «{field_name}: {name}» не найдена папка текстуры")


def _finish_texture(root: Path, name: str, field_name: str) -> str:
    directory = _directory_by_name(root, name, field_name)
    preferred = directory / f"{directory.name}_BaseColor.png"
    if preferred.is_file():
        return str(preferred)

    candidates = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() in _IMAGE_SUFFIXES
        ),
        key=lambda path: (
            "basecolor" not in path.stem.casefold(),
            path.name.casefold(),
        ),
    )
    if not candidates:
        raise ValueError(f"В папке отделки «{name}» не найдена текстура")
    return str(candidates[0])


def _metal_finish(data: dict[str, Any], metal_root: Path) -> str:
    options = data.get("options") or []
    if isinstance(options, str):
        options = [options]
    for option in options:
        match = re.search(
            r"Цвет\s+металла\s+(.+?)(?:_выбирать|$)",
            str(option),
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

    # Для старых сохранённых заказов цвет металла иногда лежит прямо в поле
    # наружной отделки.
    outside_finish = str(data.get("04_Лицо (цвет)") or "").strip()
    try:
        _directory_by_name(metal_root, outside_finish, "Цвет металла")
    except ValueError as exc:
        raise ValueError("В данных договора не удалось определить цвет металла") from exc
    return outside_finish


def _scene_texture(value: Any, default: str) -> str:
    relative = Path(str(value or default).replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Некорректный путь к текстуре стены или пола")
    if relative.parts and relative.parts[0].casefold() != "decor":
        relative = Path("decor") / relative

    decor_root = (MODULE_DIR / "decor").resolve()
    target = (MODULE_DIR / relative).resolve()
    try:
        target.relative_to(decor_root)
    except ValueError as exc:
        raise ValueError("Текстура стены или пола находится вне каталога decor") from exc
    if not target.is_file() or target.suffix.casefold() not in _IMAGE_SUFFIXES:
        raise ValueError(f"Не найдена текстура стены или пола: {relative.as_posix()}")
    return str(target)


def _frame_path(model: str, width: float, height: float) -> str:
    model_name = model.upper().replace(" ", "")
    width_int = int(round(width))
    height_int = int(round(height))
    if "SNEGIR" in model_name:
        relative = (
            Path("frame/SNEGIR/out")
            / f"Snegir_Pro_out_H{height_int}_B{width_int}.stl"
        )
    elif "S.OMEGA" in model_name or "SOMEGA" in model_name:
        relative = (
            Path("frame/S_OMEGA")
            / f"S.Omega_Delta_H{height_int}_B{width_int}.stl"
        )
    else:
        relative = (
            Path("frame/DELTA")
            / f"Gasparini_E5_H{height_int}_B{width_int}.stl"
        )

    target = MODULE_DIR / relative
    if not target.is_file():
        raise ValueError(
            f"Не найдена коробка для {model}, {width_int}×{height_int}: "
            f"{relative.as_posix()}"
        )
    return str(target)


def build_door_params(
    string_params: dict[str, Any],
    *,
    wall_texture_path: str | None = None,
    floor_texture_path: str | None = None,
    wall_texture_path_inner: str | None = None,
    floor_texture_path_inner: str | None = None,
    cutter_dxf_path: str | None = None,
    cutter_dxf_paths: dict[str, str] | None = None,
    milling_depth_mm: float = 1.5,
    milling_depths_mm: dict[str, float] | None = None,
    output_dir: str | os.PathLike[str] | None = None,
) -> DoorParams:
    """Собрать ``DoorParams`` из тела договора, текстур сцены и DXF фрез."""
    if not isinstance(string_params, dict):
        raise ValueError("Поле data должно содержать объект с данными договора")
    if "панель" in str(string_params.get("model") or "").casefold():
        raise ValueError("3D-рендер поддерживается только для дверей")

    model = _required_text(string_params, "model")
    width = _number(string_params, "01_Ширина", 0)
    height = _number(string_params, "02_Высота", 0)
    if width <= 50 or height <= 50:
        raise ValueError("Ширина и высота двери должны быть больше 50 мм")

    side_value = _required_text(string_params, "03_Петли").upper()
    is_left = "L" in side_value or "ЛЕВ" in side_value
    is_right = "R" in side_value or "ПРАВ" in side_value
    if not is_left and not is_right:
        raise ValueError(f"Не удалось определить сторону петель: {side_value}")
    side = "L" if is_left else "R"
    hinge_count = 3 if "3" in side_value or "СП" in side_value else 2

    out_color = _required_text(string_params, "04_Лицо (цвет)")
    out_pic = _required_text(string_params, "05_Лицо (рисунок)")
    in_color = _required_text(string_params, "06_Внутр. отделка (цвет)")
    in_pic = _required_text(string_params, "07_Внутр. отделка (рисунок)")
    furniture = _required_text(string_params, "08_Фурнитура")
    trim_color = _optional_finish(string_params.get("11_Обналичка (цвет)"))

    furniture_root = MODULE_DIR / "furniture"
    metal_root = MODULE_DIR / "textures" / "metal_color"
    pvc_root = MODULE_DIR / "textures" / "pvc_color"
    dxf_root = MODULE_DIR / "Pic"
    
    check_side='L' if is_left else 'R'
    

    if output_dir is None:
        order_path = Path(
            make_folder(str(string_params.get("TDOT") or "render"), str(MODULE_DIR))
        )
    else:
        order_path = Path(output_dir).resolve()
        order_path.mkdir(parents=True, exist_ok=False)

    out_dxf_name = make_scale_dxf(
        out_pic, int(round(width)), int(round(height)), str(dxf_root), str(order_path), "out", check_side
    )
    in_dxf_name = make_scale_dxf(
        in_pic, int(round(width)), int(round(height)), str(dxf_root), str(order_path), "in", check_side
    )

    is_mdf_door = "PP" in model.upper() or "NEXT" in model.upper()
    metal_color = _metal_finish(string_params, metal_root)
    frame_finish_texture_path = _finish_texture(
        metal_root, metal_color, "Цвет металла"
    )
    texture_path_inner = _finish_texture(
        pvc_root, in_color, "Внутренняя отделка (цвет)"
    )

    if is_mdf_door:
        frame_metal = False
        texture_path = _finish_texture(
            pvc_root, out_color, "Наружная отделка (цвет)"
        )
        casing_texture_path = _finish_texture(
            pvc_root,
            trim_color or out_color,
            "Обналичка (цвет)",
        )
    else:
        frame_metal = True
        texture_path = frame_finish_texture_path
        casing_texture_path = frame_finish_texture_path

    handle_obj, plate_obj, latch_obj, plate_obj2 = get_furniture_set(furniture)
    hinge_path = furniture_root / "hinge" / "pelta.stl"
    if not hinge_path.is_file():
        raise ValueError(f"Не найдена модель петли: {hinge_path}")

    peep_enabled = _flag(string_params.get("peep"))
    peephole_path = furniture_root / "Peep.obj"
    if peep_enabled and not peephole_path.is_file():
        raise ValueError(f"Не найдена модель глазка: {peephole_path}")
    peephole_pos = (
        "side-left" if _flag(string_params.get("peep_offset")) else "center"
    )

    panel_width = width - 50.0
    panel_height = height - 50.0
    return DoorParams(
        dxf_path=out_dxf_name,
        texture_path=texture_path,
        dxf_path_inner=in_dxf_name,
        texture_path_inner=texture_path_inner,
        output_path=str(order_path / "door"),
        width=panel_width,
        height=panel_height,
        pff=_number(string_params, "pff", 85.0),
        zff=_number(string_params, "zff", 85.0),
        vff=_number(string_params, "vff", 85.0),
        side=side,
        hinge_stl=str(hinge_path),
        hinge_finish=frame_finish_texture_path,
        hinge_count=hinge_count,
        # В OBJ уже указан MTL, поэтому отдельные цвета фурнитуры не нужны.
        handle_path=handle_obj,
        plate_path=plate_obj,
        plate_path2=plate_obj2,
        latch_path=latch_obj,
        frame_metal=frame_metal,
        frame_stl=_frame_path(model, width, height),
        frame_finish=casing_texture_path,
        frame_inner_finish=frame_finish_texture_path,
        wall_texture_path=_scene_texture(
            wall_texture_path, SCENE_DEFAULTS["wall_texture_path"]
        ),
        floor_texture_path=_scene_texture(
            floor_texture_path, SCENE_DEFAULTS["floor_texture_path"]
        ),
        wall_texture_path_inner=_scene_texture(
            wall_texture_path_inner,
            SCENE_DEFAULTS["wall_texture_path_inner"],
        ),
        floor_texture_path_inner=_scene_texture(
            floor_texture_path_inner,
            SCENE_DEFAULTS["floor_texture_path_inner"],
        ),
        cutter_dxf_path=cutter_dxf_path,
        cutter_dxf_paths=cutter_dxf_paths,
        milling_depth_mm=milling_depth_mm,
        milling_depths_mm=milling_depths_mm,
        peephole_path=str(peephole_path) if peep_enabled else None,
        peephole_pos=peephole_pos,
    )


def Render(
    string_params: dict[str, Any],
    *,
    wall_texture_path: str | None = None,
    floor_texture_path: str | None = None,
    wall_texture_path_inner: str | None = None,
    floor_texture_path_inner: str | None = None,
    cutter_dxf_path: str | None = None,
    cutter_dxf_paths: dict[str, str] | None = None,
    milling_depth_mm: float = 1.5,
    milling_depths_mm: dict[str, float] | None = None,
    output_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Сформировать параметры из тела договора и запустить рендер."""
    params = build_door_params(
        string_params,
        wall_texture_path=wall_texture_path,
        floor_texture_path=floor_texture_path,
        wall_texture_path_inner=wall_texture_path_inner,
        floor_texture_path_inner=floor_texture_path_inner,
        cutter_dxf_path=cutter_dxf_path,
        cutter_dxf_paths=cutter_dxf_paths,
        milling_depth_mm=milling_depth_mm,
        milling_depths_mm=milling_depths_mm,
        output_dir=output_dir,
    )
    results = generate_door(params)
    return {
        "params": params,
        "results": results,
        "images": {
            "out": f"{params.output_path}_out.png",
            "in": f"{params.output_path}_in.png",
        },
    }
    

def make_folder(tdot, current_dir):
    base_dir = Path(current_dir) / "ORDERS"
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S%f")
    safe_tdot = re.sub(r"[^0-9A-Za-zА-Яа-я_-]+", "_", str(tdot)).strip("_")
    folder_path = base_dir / f"{safe_tdot or 'render'}_{timestamp}"
    folder_path.mkdir(parents=True, exist_ok=False)
    return str(folder_path)

def make_scale_dxf(name_dxf, width, height, dxf_path, order_path, inout, check_side):
    from scale import scale_panel_by_opening
    
    # Формируем имя исходного и конечного файла
    source_filename = f"{name_dxf}_{inout}.dxf"
    output_filename = f"{name_dxf}_{inout}.dxf"
    
    source_path = os.path.join(dxf_path, source_filename)
    final_output_path = os.path.join(order_path, output_filename)

    opening_width=int(width)
    opening_height=int(height)
    
    if not os.path.isfile(source_path):
        raise ValueError(f"Не найден исходный DXF: {source_path}")
    result = scale_panel_by_opening(
        source_path,
        order_path,
        opening_width,
        opening_height,
        check_side,
        output_filename=output_filename
    )
    if result is None or not os.path.isfile(final_output_path):
        raise RuntimeError(f"Не удалось подготовить DXF: {source_path}")
    return final_output_path


def get_furniture_set(furniture_abbr):
    """
    Возвращает OBJ четырёх элементов комплекта в строгом порядке:
    handle_obj, plate_obj, latch_obj, plate_obj2.

    Каждый OBJ обязан иметь одноимённый MTL. Цвета фурнитуры отдельно
    не передаются: экспортер забирает материалы непосредственно из MTL.
    
    Args:
        furniture_abbr (str): Аббревиатура комплекта
    
    Returns:
        tuple: (handle_obj, plate_obj, latch_obj, plate_obj2)
    """
    
    # Словарь со всеми комплектами - порядок элементов строго соблюдается!
    furniture_sets = {
        "ХКР_МОН_ALFA": [
            "Handle_INSPECTOR 93, Intecron_cr.obj",  # handle_stl
            "Nakl_cyl_ Intecron_MOH-L F_cr.obj",      # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_so_sht_Intecron_cr.obj"         # plate_stl2
        ],
        "ХКР_МОН 3D_ALFA": [
            "Handle_Apecs H-1582_cr.obj",             # handle_stl
            "Nakl_suv_so_sht_Intecron_cr.obj",        # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_so_sht_Intecron_cr.obj"         # plate_stl2
        ],
        "ЧКВ_AP15_AP15": [
            "Handle_Apecs H-1582_bl.obj",             # handle_stl
            "Nakl_shtok_Apecs DP-15_bl.obj",          # plate_stl
            "Pov_75mm_Apecs TT-1516.mini_bl.obj",     # latch_stl
            "Nakl_cyl_Avers DP-15.mini_bl.obj"        # plate_stl2
        ],
        "ХКР_МОН_BOSTON": [
            "Handle_BOSTON AR SN_CP-3_cr.obj",        # handle_stl
            "Nakl_cyl_ Intecron_MOH-L F_cr.obj",      # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_so_sht_Intecron_cr.obj"         # plate_stl2
        ],
        "ХКР_БН МОН_ALFA": [
            "Handle_INSPECTOR 93, Intecron_cr.obj",   # handle_stl
            "brn_pustotelaya_cr.obj",                 # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_so_sht_Intecron_cr.obj"         # plate_stl2
        ],
        "ХКР_БН МОН_BOSTON": [
            "Handle_BOSTON AR SN_CP-3_cr.obj",        # handle_stl
            "brn_pustotelaya_cr.obj",                 # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_so_sht_Intecron_cr.obj"         # plate_stl2
        ],
        "ЧКВ_БН AP15_AP15": [
            "Handle_Apecs H-1582_bl.obj",             # handle_stl
            "brn_Avers Pro 50_11-DP-15_bl.obj",       # plate_stl
            "Pov_75mm_Apecs TT-1516.mini_bl.obj",     # latch_stl
            "Nakl_cyl_Avers DP-15.mini_bl.obj"        # plate_stl2
        ],
        "ХКВ_БН TORXL_TORXL": [
            "Handle_Apecs H-1582_cr.obj",             # handle_stl
            "brn_Avers Pro 50_11-DP-15_cr.obj",       # plate_stl
            "Pov_75mm_Apecs TT-1516-8_75-CRS_cr.obj", # latch_stl
            "Nakl_suv_s_avt_sht_Apecs_cr.obj"         # plate_stl2
        ],
        "ХКВ_TORXL_TORXL": [
            "Handle_Apecs H-1582_cr.obj",             # handle_stl
            "Nakl_shtok_Fuaro ESC 486_cr.obj",        # plate_stl
            "Pov_75mm_Apecs TT-1516-8_75-CRS_cr.obj", # latch_stl
            "Nakl_suv_s_avt_sht_Apecs_cr.obj"         # plate_stl2
        ],
        "ХКР_МОН 3D_LARGO": [
            "Handle_LARGO RM SN_CP_cr.obj",           # handle_stl
            "Nakl_suv_Intecron_MOH-3D_cr.obj",        # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_Krit_Kl_C13_22_cr.obj"          # plate_stl2
        ],
        "ХКР_БН КлС_LARGO": [
            "Handle_LARGO RM SN_CP_cr.obj",           # handle_stl
            "brn_26_cr.obj",                          # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_Krit_Kl_C13_cr.obj"             # plate_stl2
        ],
        "ХКР_МОН 3D_PAVA": [
            "Handle_Pava LDР42-1CP-8 TECH)_cr.obj",   # handle_stl
            "Nakl_suv_Intecron_MOH-3D_cr.obj",        # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_Krit_Kl_C13_cr.obj"             # plate_stl2
        ],
        "ХКР_БН КлС_PAVA": [
            "Handle_Pava LDР42-1CP-8 TECH)_cr.obj",   # handle_stl
            "brn_26_cr.obj",                          # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_Krit_Kl_C13_cr.obj"             # plate_stl2
        ],
        "ХКР_МОН_PAVA": [
            "Handle_Pava LDР42-1CP-8 TECH)_cr.obj",   # handle_stl
            "Nakl_suv_Intecron_MOH-3D_cr.obj",        # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_Krit_Kl_C13_cr.obj"             # plate_stl2
        ],
        "ЧКВ_USS_SKY": [
            "Handle_Armadillo SKY USS BL-26_bl.obj",  # handle_stl
            "Nakl_suv_Armadillo PS Protector_USS BL_bl.obj",  # plate_stl
            "Pov_75mm_Armadilo BKW8_USS BL-26_bl.obj",        # latch_stl
            "Nakl_suv_Armadillo PS Protector_USS BL_bl.obj"   # plate_stl2
        ],
        "ЧКВ_БН USS_SKY": [
            "Handle_Armadillo SKY USS BL-26_bl.obj",  # handle_stl
            "brn_Armadillo Protector_USS BL (42983)_bl.obj",  # plate_stl
            "Pov_75mm_Armadilo BKW8_USS BL-26_bl.obj",        # latch_stl
            "Nakl_suv_Armadillo PS Protector_USS BL_bl.obj"   # plate_stl2
        ],
        "ХКВ_БН USS_SKY": [
            "Handle_Armadillo SKY USS BL-26_cr.obj",  # handle_stl
            "brn_Armadillo Protector_USS BL_cr.obj",  # plate_stl
            "Pov_75mm_Armadilo BKW8_USS BL-26_cr.obj",        # latch_stl
            "Nakl_suv_Armadillo PS Protector_USS BL_cr.obj"   # plate_stl2
        ],
        "ХКР_БН КлС_KEA": [
            "Handle_KEA (20341)_cr.obj",              # handle_stl
            "brn_26_cr.obj",                          # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_Krit_Kl_C13_cr.obj"             # plate_stl2
        ],
        "ХКР_БН КлС_HOPPE": [
            "Handle_Hoppe vitoria (65892)_cr.obj",    # handle_stl
            "brn_26_cr.obj",                          # plate_stl
            "Pov_50mm_plast_cr.obj",                  # latch_stl
            "Nakl_suv_Krit_Kl_C13_22_cr.obj"          # plate_stl2
        ]
    }
    
    aliases = {
        # В старой расшифровке перед LARGO встречался лишний пробел.
        "ХКР_БН КлС _LARGO": "ХКР_БН КлС_LARGO",
    }
    key = aliases.get(str(furniture_abbr), str(furniture_abbr))
    files = furniture_sets.get(key)
    if not files:
        raise ValueError(f"Комплект фурнитуры «{furniture_abbr}» не расшифрован")

    paths = tuple(MODULE_DIR / "furniture" / filename for filename in files)
    for obj_path in paths:
        if not obj_path.is_file():
            raise ValueError(f"Не найден OBJ фурнитуры: {obj_path.name}")
        mtl_path = obj_path.with_suffix(".mtl")
        if not mtl_path.is_file():
            raise ValueError(f"Для OBJ фурнитуры не найден MTL: {mtl_path.name}")
    return tuple(str(path) for path in paths)


def _authorized(http_request) -> bool:
    expected = os.environ.get("RENDER_API_TOKEN", "")
    if not expected:
        return True
    provided = http_request.headers.get("X-API-Key", "")
    return hmac.compare_digest(provided, expected)


def _result_image(request_id: str, side: str) -> Path:
    if not _REQUEST_ID_RE.fullmatch(request_id):
        raise ValueError("Некорректный идентификатор рендера")
    if side not in {"out", "in"}:
        raise ValueError("Некорректная сторона двери")
    return MODULE_DIR / "ORDERS" / request_id / f"door_{side}.png"


def create_app():
    """Создать HTTP API RENDER_NEW для WEB_NST."""
    from flask import Flask, jsonify, request, send_file, url_for

    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"success": True, "service": "RENDER_NEW"})

    @app.post("/render")
    def render_http():
        if not _authorized(request):
            return jsonify({"success": False, "error": "Неверный API-ключ"}), 401

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            return jsonify(
                {
                    "success": False,
                    "error": "Ожидается тело запроса с объектом data договора",
                }
            ), 400

        request_id = uuid.uuid4().hex
        output_dir = MODULE_DIR / "ORDERS" / request_id
        try:
            rendered = Render(
                payload["data"],
                wall_texture_path=payload.get("wall_texture_path"),
                floor_texture_path=payload.get("floor_texture_path"),
                wall_texture_path_inner=payload.get("wall_texture_path_inner"),
                floor_texture_path_inner=payload.get("floor_texture_path_inner"),
                cutter_dxf_path=payload.get("cutter_dxf_path"),
                cutter_dxf_paths=payload.get("cutter_dxf_paths"),
                milling_depth_mm=payload.get("milling_depth_mm", 1.5),
                milling_depths_mm=payload.get("milling_depths_mm"),
                output_dir=output_dir,
            )
            missing = [
                side
                for side, image_path in rendered["images"].items()
                if not Path(image_path).is_file()
            ]
            if missing:
                raise RuntimeError(
                    "Не созданы изображения сторон двери: " + ", ".join(missing)
                )
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Ошибка RENDER_NEW")
            return jsonify({"success": False, "error": str(exc)}), 500

        return jsonify(
            {
                "success": True,
                "request_id": request_id,
                "images": {
                    side: url_for(
                        "render_result",
                        request_id=request_id,
                        side=side,
                    )
                    for side in ("out", "in")
                },
            }
        )

    @app.get("/render-results/<request_id>/<side>.png")
    def render_result(request_id: str, side: str):
        if not _authorized(request):
            return jsonify({"success": False, "error": "Неверный API-ключ"}), 401
        try:
            image_path = _result_image(request_id, side)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404
        if not image_path.is_file():
            return jsonify({"success": False, "error": "Изображение не найдено"}), 404
        return send_file(image_path, mimetype="image/png", conditional=True)

    return app


def _parse_server_args():
    parser = argparse.ArgumentParser(description="HTTP API модуля RENDER_NEW")
    parser.add_argument(
        "--host",
        default=os.environ.get("RENDER_HOST", "127.0.0.1"),
        help="Адрес HTTP-сервера",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("RENDER_PORT", "5001")),
        help="Порт HTTP-сервера",
    )
    return parser.parse_args()


if __name__ == "__main__":
    server_args = _parse_server_args()
    create_app().run(
        host=server_args.host,
        port=server_args.port,
        debug=False,
        threaded=True,
    )
