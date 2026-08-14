"""
Модуль для расшифровки аббревиатур комплектов фурнитуры в реальные файлы.
"""
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent


def get_furniture_set(furniture_abbr: str) -> dict[str, list[str]]:
    """
    Возвращает OBJ-файлы для комплекта фурнитуры, разделенные для наружной и внутренней стороны.

    Каждый OBJ обязан иметь одноимённый MTL. Цвета фурнитуры отдельно
    не передаются: экспортер забирает материалы непосредственно из MTL.

    Args:
        furniture_abbr (str): Аббревиатура комплекта.

    Returns:
        dict: Словарь с ключами 'out' и 'in'.
              - 'out': [handle, main_lock_plate, adv_lock_plate]
              - 'in': [handle, main_lock_plate, adv_lock_plate, latch]
    """

    # Словарь со всеми комплектами
    # out: [ручка, накладка осн. замка, накладка доп. замка]
    # in:  [ручка, накладка осн. замка, накладка доп. замка, задвижка]
    furniture_sets = {
        "ХКР_МОН_ALFA": {
            "out": ["Handle_INSPECTOR 93, Intecron_cr.obj", "Nakl_cyl_ Intecron_MOH-L F_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj"],
            "in": ["Handle_INSPECTOR 93, Intecron_cr.obj", "Nakl_cyl_ Intecron_MOH-L F_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ХКР_МОН 3D_ALFA": {
            "out": ["Handle_Apecs H-1582_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj"],
            "in": ["Handle_Apecs H-1582_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ЧКВ_AP15_AP15": {
            "out": ["Handle_Apecs H-1582_bl.obj", "Nakl_shtok_Apecs DP-15_bl.obj", "Nakl_cyl_Avers DP-15.mini_bl.obj"],
            "in": ["Handle_Apecs H-1582_bl.obj", "Nakl_shtok_Apecs DP-15_bl.obj", "Nakl_cyl_Avers DP-15.mini_bl.obj", "Pov_75mm_Apecs TT-1516.mini_bl.obj"]
        },
        "ХКР_МОН_BOSTON": {
            "out": ["Handle_BOSTON AR SN_CP-3_cr.obj", "Nakl_cyl_ Intecron_MOH-L F_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj"],
            "in": ["Handle_BOSTON AR SN_CP-3_cr.obj", "Nakl_cyl_ Intecron_MOH-L F_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ХКР_БН МОН_ALFA": {
            "out": ["Handle_INSPECTOR 93, Intecron_cr.obj", "brn_pustotelaya_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj"],
            "in": ["Handle_INSPECTOR 93, Intecron_cr.obj", "brn_pustotelaya_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ХКР_БН МОН_BOSTON": {
            "out": ["Handle_BOSTON AR SN_CP-3_cr.obj", "brn_pustotelaya_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj"],
            "in": ["Handle_BOSTON AR SN_CP-3_cr.obj", "brn_pustotelaya_cr.obj", "Nakl_suv_so_sht_Intecron_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ЧКВ_БН AP15_AP15": {
            "out": ["Handle_Apecs H-1582_bl.obj", "brn_Avers Pro 50_11-DP-15_bl.obj", "Nakl_cyl_Avers DP-15.mini_bl.obj"],
            "in": ["Handle_Apecs H-1582_bl.obj", "brn_Avers Pro 50_11-DP-15_bl.obj", "Nakl_cyl_Avers DP-15.mini_bl.obj", "Pov_75mm_Apecs TT-1516.mini_bl.obj"]
        },
        "ХКВ_БН TORXL_TORXL": {
            "out": ["Handle_Apecs H-1582_cr.obj", "brn_Avers Pro 50_11-DP-15_cr.obj", "Nakl_suv_s_avt_sht_Apecs_cr.obj"],
            "in": ["Handle_Apecs H-1582_cr.obj", "brn_Avers Pro 50_11-DP-15_cr.obj", "Nakl_suv_s_avt_sht_Apecs_cr.obj", "Pov_75mm_Apecs TT-1516-8_75-CRS_cr.obj"]
        },
        "ХКВ_TORXL_TORXL": {
            "out": ["Handle_Apecs H-1582_cr.obj", "Nakl_shtok_Fuaro ESC 486_cr.obj", "Nakl_suv_s_avt_sht_Apecs_cr.obj"],
            "in": ["Handle_Apecs H-1582_cr.obj", "Nakl_shtok_Fuaro ESC 486_cr.obj", "Nakl_suv_s_avt_sht_Apecs_cr.obj", "Pov_75mm_Apecs TT-1516-8_75-CRS_cr.obj"]
        },
        "ХКР_МОН 3D_LARGO": {
            "out": ["Handle_LARGO RM SN_CP_cr.obj", "Nakl_suv_Intecron_MOH-3D_cr.obj", "Nakl_suv_Krit_Kl_C13_22_cr.obj"],
            "in": ["Handle_LARGO RM SN_CP_cr.obj", "Nakl_suv_Intecron_MOH-3D_cr.obj", "Nakl_suv_Krit_Kl_C13_22_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ХКР_БН КлС_LARGO": {
            "out": ["Handle_LARGO RM SN_CP_cr.obj", "brn_26_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj"],
            "in": ["Handle_LARGO RM SN_CP_cr.obj", "brn_26_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ХКР_МОН 3D_PAVA": {
            "out": ["Handle_Pava LDР42-1CP-8 TECH)_cr.obj", "Nakl_suv_Intecron_MOH-3D_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj"],
            "in": ["Handle_Pava LDР42-1CP-8 TECH)_cr.obj", "Nakl_suv_Intecron_MOH-3D_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ХКР_БН КлС_PAVA": {
            "out": ["Handle_Pava LDР42-1CP-8 TECH)_cr.obj", "brn_26_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj"],
            "in": ["Handle_Pava LDР42-1CP-8 TECH)_cr.obj", "brn_26_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ХКР_МОН_PAVA": {
            "out": ["Handle_Pava LDР42-1CP-8 TECH)_cr.obj", "Nakl_suv_Intecron_MOH-3D_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj"],
            "in": ["Handle_Pava LDР42-1CP-8 TECH)_cr.obj", "Nakl_suv_Intecron_MOH-3D_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ЧКВ_USS_SKY": {
            "out": ["Handle_Armadillo SKY USS BL-26_bl.obj", "Nakl_suv_Armadillo PS Protector_USS BL_bl.obj", "Nakl_suv_Armadillo PS Protector_USS BL_bl.obj"],
            "in": ["Handle_Armadillo SKY USS BL-26_bl.obj", "Nakl_suv_Armadillo PS Protector_USS BL_bl.obj", "Nakl_suv_Armadillo PS Protector_USS BL_bl.obj", "Pov_75mm_Armadilo BKW8_USS BL-26_bl.obj"]
        },
        "ЧКВ_БН USS_SKY": {
            "out": ["Handle_Armadillo SKY USS BL-26_bl.obj", "brn_Armadillo Protector_USS BL (42983)_bl.obj", "Nakl_suv_Armadillo PS Protector_USS BL_bl.obj"],
            "in": ["Handle_Armadillo SKY USS BL-26_bl.obj", "brn_Armadillo Protector_USS BL (42983)_bl.obj", "Nakl_suv_Armadillo PS Protector_USS BL_bl.obj", "Pov_75mm_Armadilo BKW8_USS BL-26_bl.obj"]
        },
        "ХКВ_БН USS_SKY": {
            "out": ["Handle_Armadillo SKY USS BL-26_cr.obj", "brn_Armadillo Protector_USS BL_cr.obj", "Nakl_suv_Armadillo PS Protector_USS BL_cr.obj"],
            "in": ["Handle_Armadillo SKY USS BL-26_cr.obj", "brn_Armadillo Protector_USS BL_cr.obj", "Nakl_suv_Armadillo PS Protector_USS BL_cr.obj", "Pov_75mm_Armadilo BKW8_USS BL-26_cr.obj"]
        },
        "ХКР_БН КлС_KEA": {
            "out": ["Handle_KEA (20341)_cr.obj", "brn_26_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj"],
            "in": ["Handle_KEA (20341)_cr.obj", "brn_26_cr.obj", "Nakl_suv_Krit_Kl_C13_cr.obj", "Pov_50mm_plast_cr.obj"]
        },
        "ХКР_БН КлС_HOPPE": {
            "out": ["Handle_Hoppe vitoria (65892)_cr.obj", "brn_26_cr.obj", "Nakl_suv_Krit_Kl_C13_22_cr.obj"],
            "in": ["Handle_Hoppe vitoria (65892)_cr.obj", "brn_26_cr.obj", "Nakl_suv_Krit_Kl_C13_22_cr.obj", "Pov_50mm_plast_cr.obj"]
        }
    }

    aliases = {
        # В старой расшифровке перед LARGO встречался лишний пробел.
        "ХКР_БН КлС _LARGO": "ХКР_БН КлС_LARGO",
    }

    key = aliases.get(str(furniture_abbr), str(furniture_abbr))
    file_sets = furniture_sets.get(key)
    if not file_sets:
        raise ValueError(f"Комплект фурнитуры «{furniture_abbr}» не расшифрован")

    # Проверяем наличие файлов и формируем абсолютные пути
    result = {"out": [], "in": []}
    furniture_root = MODULE_DIR / "furniture"

    for side in ["out", "in"]:
        for filename in file_sets[side]:
            obj_path = furniture_root / filename
            if not obj_path.is_file():
                raise ValueError(f"Не найден OBJ фурнитуры: {obj_path.name}")

            mtl_path = obj_path.with_suffix(".mtl")
            if not mtl_path.is_file():
                raise ValueError(f"Для OBJ фурнитуры не найден MTL: {mtl_path.name}")

            result[side].append(str(obj_path))

    return result