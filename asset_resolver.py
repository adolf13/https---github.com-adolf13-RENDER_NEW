"""Разрешение названий отделок WEB_NST в файлы текстур RENDER_NEW.

Модуль намеренно не импортирует Open3D и остальную часть рендера: WEB_NST
загружает его отдельно для быстрых миниатюр в выпадающих списках.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
_FINISH_DIRECTORIES = (
    Path("textures/pvc_color"),
    Path("textures/metal_color"),
)


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = value.casefold().replace("ё", "е")
    return re.sub(r"\s+", " ", value).strip(" ._-")


def _texture_file(directory: Path, finish_name: str) -> Path:
    preferred = directory / f"{directory.name}_BaseColor.png"
    if preferred.is_file():
        return preferred

    candidates = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() in _IMAGE_SUFFIXES
        ),
        key=lambda path: (
            "basecolor" not in _normalized(path.stem),
            path.name.casefold(),
        ),
    )
    if not candidates:
        raise FileNotFoundError(
            f"В каталоге отделки «{finish_name}» нет файла изображения"
        )
    return candidates[0]


def resolve_texture_name(
    module_root: str | Path,
    finish_name: str,
    field_name: str = "Отделка",
) -> str:
    """Вернуть безопасный путь к BaseColor относительно корня RENDER_NEW."""
    root = Path(module_root).resolve()
    target_name = _normalized(finish_name)
    if not target_name or target_name in {"выбрать", "no_data", "none"}:
        raise ValueError(f"Не выбрано значение поля «{field_name}»")

    matches: list[Path] = []
    for relative_root in _FINISH_DIRECTORIES:
        finish_root = (root / relative_root).resolve()
        if not finish_root.is_dir():
            continue
        for directory in finish_root.iterdir():
            if directory.is_dir() and _normalized(directory.name) == target_name:
                matches.append(directory)

    if not matches:
        raise FileNotFoundError(
            f"Для «{field_name}: {finish_name}» текстура в RENDER_NEW не найдена"
        )
    if len(matches) > 1:
        variants = ", ".join(path.name for path in matches)
        raise ValueError(
            f"Для «{field_name}: {finish_name}» найдено несколько текстур: "
            f"{variants}"
        )

    texture = _texture_file(matches[0], finish_name).resolve()
    try:
        return texture.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Текстура находится вне каталога RENDER_NEW") from exc
