"""Преобразование тела договора WEB_NST в параметры RENDER_NEW.

WEB_NST передаёт словарь ``data`` без преобразований. Дополнительно запрос
содержит только четыре выбранные текстуры стены и пола. Вся расшифровка
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
from furniture_resolver import get_furniture_set


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


def _directory_by_name(roots: list[Path], name: str, field_name: str) -> Path:
    """Ищет директорию с текстурой в нескольких корневых каталогах."""
    normalized = name.strip().casefold().replace("ё", "е")
    found_paths = []
    for root in roots:
        if not root.is_dir():
            continue
        for directory in root.iterdir():
            candidate = directory.name.casefold().replace("ё", "е")
            if directory.is_dir() and candidate == normalized:
                found_paths.append(directory)
    
    if len(found_paths) == 1:
        return found_paths[0]
    if len(found_paths) > 1:
        raise ValueError(f"Для «{field_name}: {name}» найдено несколько папок текстур")
    raise ValueError(f"Для «{field_name}: {name}» не найдена папка текстуры")


def _finish_texture(roots: list[Path], name: str, field_name: str) -> str:
    directory = _directory_by_name(roots, name, field_name)
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
    # Новое правило: для дверей NEXT цвет металла = цвет обналички
    model = str(data.get("model") or "").upper()
    if "NEXT" in model:
        trim_color = _optional_finish(data.get("11_Обналичка (цвет)"))
        if trim_color:
            try:
                _directory_by_name([metal_root], trim_color, "Обналичка (цвет)")
                return trim_color
            except ValueError:
                pass  # Если цвет обналички не найден как цвет металла, используем старую логику

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
        _directory_by_name([metal_root], outside_finish, "Цвет металла")
    except ValueError as exc:
        raise ValueError("В данных договора не удалось определить цвет металла") from exc
    return outside_finish


def _scene_texture(value: Any, default: str) -> str:
    relative = Path(str(value or default).replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Некорректный путь к текстуре стены или пола")
    if relative.parts and relative.parts[0].casefold() != "decor":
        relative = Path("decor") / relative

    decor_root = (MODULE_DIR.parent / "decor").resolve()
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

    target = MODULE_DIR.parent / relative
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
    output_dir: str | os.PathLike[str] | None = None,
) -> DoorParams:
    """Собрать ``DoorParams`` только из тела договора и текстур сцены."""
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

    furniture_root = MODULE_DIR.parent / "furniture"
    metal_root = MODULE_DIR.parent / "textures" / "metal_color"
    pvc_root = MODULE_DIR.parent / "textures" / "pvc_color"
    dxf_root = MODULE_DIR.parent / "Pic"
    
    check_side='L' if is_left else 'R'
    

    if output_dir is None:
        order_path = Path(
            make_folder(str(string_params.get("TDOT") or "render"), str(MODULE_DIR))
        )
    else:
        order_path = Path(output_dir).resolve()
        order_path.mkdir(parents=True, exist_ok=False)



    # здесь делается dxf для накладки  ==================================================================
    # В конце out_dxf_name и in_dxf_name получают имена с dxf файлами накладок. Нам нужно: если для рисунка готов новый метод
    # обработки - запустить его (MakePanel/main.py), иначе использовать старый метод (make_scale_dxf).

    out_dxf_name = prepare_dxf(model, out_pic, width, height, check_side, "out", str(dxf_root), str(order_path))
    in_dxf_name = prepare_dxf(model, in_pic, width, height, check_side, "in", str(dxf_root), str(order_path))

    # ==================================================================

    is_mdf_door = "PP" in model.upper() or "NEXT" in model.upper()
    metal_color = _metal_finish(string_params, metal_root)
    frame_finish_texture_path = _finish_texture(
        [metal_root], metal_color, "Цвет металла"
    )
    texture_path_inner = _finish_texture(
        [pvc_root], in_color, "Внутренняя отделка (цвет)"
    )

    if is_mdf_door:
        frame_metal = False
        texture_path = _finish_texture(
            [pvc_root], out_color, "Наружная отделка (цвет)"
        )
        casing_texture_path = _finish_texture(
            [pvc_root, metal_root],  # Искать и в PVC, и в METAL
            trim_color or out_color,
            "Обналичка (цвет)",
        )
    else:
        frame_metal = True
        texture_path = frame_finish_texture_path
        casing_texture_path = frame_finish_texture_path

    furniture_paths = get_furniture_set(furniture)
    handle_out, nakl_main_out, nakl_adv_out = furniture_paths["out"]
    handle_in, nakl_main_in, nakl_adv_in, latch = furniture_paths["in"]

    hinge_path = furniture_root / "hinge" / "pelta.stl"
    if not hinge_path.is_file():
        raise ValueError(f"Не найдена модель петли: {hinge_path}")

    peep_enabled = _flag(string_params.get("peep"))
    peephole_path = furniture_root / "Peep.obj"
    if peep_enabled and not peephole_path.is_file():
        raise ValueError(f"Не найдена модель глазка: {peephole_path}")
    peephole_offset_flag = _flag(string_params.get("peep_offset"))

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
        model=model,
        side=side,
        hinge_stl=str(hinge_path),
        hinge_finish=frame_finish_texture_path,
        hinge_count=hinge_count,
        # В OBJ уже указан MTL, поэтому отдельные цвета фурнитуры не нужны.
        handle_path_out=handle_out,
        nakl_main_lock_out=nakl_main_out,
        nakl_adv_lock_out=nakl_adv_out,
        handle_path_in=handle_in,
        nakl_main_lock_in=nakl_main_in,
        nakl_adv_lock_in=nakl_adv_in,
        latch_path=latch,
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
        peephole_path=str(peephole_path) if peep_enabled else None,
        peephole_offset=peephole_offset_flag,
    )


def Render(
    string_params: dict[str, Any],
    *,
    wall_texture_path: str | None = None,
    floor_texture_path: str | None = None,
    wall_texture_path_inner: str | None = None,
    floor_texture_path_inner: str | None = None,
    output_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Сформировать параметры из тела договора и запустить рендер."""
    params = build_door_params(
        string_params,
        wall_texture_path=wall_texture_path,
        floor_texture_path=floor_texture_path,
        wall_texture_path_inner=wall_texture_path_inner,
        floor_texture_path_inner=floor_texture_path_inner,
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

def prepare_dxf(model, pic_name, width, height, side, inout, dxf_root_path, order_path):
    """
    Подготавливает DXF файл, выбирая между новым алгоритмом и старым масштабированием.
    """
    from MakePanel.main import MakePanel
    from scale import scale_panel_by_opening

    list_ready_pics = ['L01', 'L02', 'L03', 'L04', 'L05', 'L07', 'L10', 'L11', 'L12', 'C01', 'C02', 'C03', 'NC1', 'NC2', 'NC3']
    
    use_new_alg = any(name in pic_name for name in list_ready_pics)

    output_filename = f"{pic_name}_{inout}.dxf"
    final_output_path = os.path.join(order_path, output_filename)

    if use_new_alg:
        print(f"🚀 Запуск нового алгоритма для рисунка '{pic_name}'...")
        # Новый алгоритм сам обрабатывает inout и сохраняет файл
        MakePanel(model, f"{pic_name}_{inout}", side, width, height, final_output_path)
        if not os.path.isfile(final_output_path):
            raise RuntimeError(f"Новый алгоритм не создал DXF файл: {final_output_path}")
    else:
        print(f"↔️  Запуск старого алгоритма масштабирования для '{pic_name}'...")
        source_filename = f"{pic_name}_{inout}.dxf"
        source_path = os.path.join(dxf_root_path, source_filename)

        if not os.path.isfile(source_path):
            raise ValueError(f"Не найден исходный DXF для масштабирования: {source_path}")

        result = scale_panel_by_opening(
            source_path,
            order_path,
            width,
            height,
            side,
            output_filename=output_filename
        )
        if result is None or not os.path.isfile(final_output_path):
            raise RuntimeError(f"Не удалось масштабировать DXF: {source_path}")

    return final_output_path


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
