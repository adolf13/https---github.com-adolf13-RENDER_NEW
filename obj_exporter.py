"""
Экспорт OBJ/MTL файлов
"""
import os
import shutil
import numpy as np
import open3d as o3d
from collections import defaultdict
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def write_obj_with_materials(filename, meshes, material_props=None):
    """
    Экспортирует меши в OBJ/MTL
    
    Args:
        filename: Путь к OBJ файлу
        meshes: Список кортежей (mesh, material_name, texture_path)
        material_props: Словарь с параметрами материалов
    """
    obj_path = filename
    mtl_path = os.path.splitext(obj_path)[0] + ".mtl"
    mtl_name = os.path.basename(mtl_path)
    
    # Множество для отслеживания уже скопированных текстур
    copied_textures = set()

    def parse_mtl(file_path):
        """Парсит MTL файл и возвращает словарь материалов и их свойств."""
        materials = {}
        if not os.path.exists(file_path):
            return materials
        
        current_material = None
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == 'newmtl':
                    current_material = parts[1]
                    materials[current_material] = []
                elif current_material is not None:
                    materials[current_material].append(line)
        return materials

    def copy_texture(src_path, dst_dir):
        """Копирует текстуру в целевую директорию, если она еще не была скопирована"""
        if not os.path.exists(src_path):
            return None
            
        tex_filename = os.path.basename(src_path)
        dst_path = os.path.join(dst_dir, tex_filename)
        
        # Проверяем, не копировали ли уже эту текстуру
        if src_path in copied_textures:
            return tex_filename
            
        # Если файлы разные, копируем
        if os.path.abspath(src_path) != os.path.abspath(dst_path):
            try:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                copied_textures.add(src_path)
                print(f"📁 Скопирована текстура: {tex_filename}")
            except Exception as e:
                print(f"⚠️ Не удалось скопировать текстуру {tex_filename}: {e}")
                return None
                
        return tex_filename

    # --- Собираем информацию о материалах ---
    material_data = {}

    for mesh, mat, tex in meshes:
        # --- Обработка фурнитуры с вложенными материалами ---
        if mat and tex and tex.lower().endswith('.obj'):
            original_obj_path = tex
            original_mtl_path = os.path.splitext(original_obj_path)[0] + ".mtl"
            
            # Парсим оригинальный MTL-файл, чтобы получить свойства
            original_mtl_props = parse_mtl(original_mtl_path)
            original_material_names = list(original_mtl_props.keys())
            
            if not original_material_names:
                print(f"⚠️ В файле {original_mtl_path} не найдено материалов")
                continue
            
            # Создаем уникальные материалы с префиксом
            for orig_mat_name in original_material_names:
                new_mat_name = f"{mat}_{orig_mat_name}"
                if new_mat_name not in material_data:
                    material_data[new_mat_name] = {
                        'properties': original_mtl_props.get(orig_mat_name, []),
                        'source_dir': os.path.dirname(original_mtl_path),
                        'is_embedded': True
                    }
            continue  # Переходим к следующему мешу
            
        # --- Стандартная обработка материалов ---
        if mat is None:
            continue
            
        if mat not in material_data:
            # Получаем цвет из material_props
            if material_props and mat in material_props:
                texture = material_props[mat].get("texture", tex)
            else:
                texture = tex

            # Если текстура указана, но файл не существует - игнорируем
            if texture and not os.path.exists(texture):
                print(f"⚠️ Текстура не найдена: {texture}")
                texture = None
            
            material_data[mat] = {
                'texture': texture,
                'is_embedded': False
            }

            print(f"📦 Материал {mat}: текстура={texture}")

    # --- Пишем MTL файл ---
    os.makedirs(os.path.dirname(obj_path), exist_ok=True)
    
    with open(mtl_path, "w", encoding='utf-8') as mtl:
        mtl.write("# MTL файл\n")
        mtl.write("# Сгенерировано OBJExporter\n\n")

        for mat_name, data in material_data.items():
            mtl.write(f"\nnewmtl {mat_name}\n")

            # Если есть свойства из оригинального MTL, используем их
            if data.get('is_embedded') and 'properties' in data and data['properties']:
                source_dir = data.get('source_dir', '')
                for prop_line in data['properties']:
                    parts = prop_line.split()
                    if len(parts) > 1 and parts[0] in ('map_Kd', 'map_Ks', 'map_Ka', 'map_bump', 'bump'):
                        tex_name = parts[1]
                        src_tex_path = os.path.join(source_dir, tex_name)
                        # Копируем текстуру
                        copy_texture(src_tex_path, os.path.dirname(obj_path))
                    mtl.write(f"{prop_line}\n")
                    
            elif material_props and mat_name in material_props:
                # Используем свойства из material_props (например, chrome_props)
                prop_data = material_props[mat_name]
                color = prop_data.get("color", (0.8, 0.8, 0.8))
                ks = prop_data.get("Ks", (0.1, 0.1, 0.1))
                ns = prop_data.get("Ns", 10.0)
                mtl.write(f"Kd {color[0]:.4f} {color[1]:.4f} {color[2]:.4f}\n")
                mtl.write(f"Ka {color[0]*0.1:.4f} {color[1]*0.1:.4f} {color[2]*0.1:.4f}\n")
                mtl.write(f"Ks {ks[0]:.4f} {ks[1]:.4f} {ks[2]:.4f}\n")
                mtl.write(f"Ns {ns:.1f}\n")
                texture = data.get('texture')
                
                # Копируем текстуру, если она есть
                if texture and os.path.exists(texture):
                    tex_filename = copy_texture(texture, os.path.dirname(obj_path))
                    if tex_filename:
                        mtl.write(f"map_Kd {tex_filename}\n")
                        
            # Для стандартных материалов с текстурой
            elif not data.get('is_embedded') and data.get('texture'):
                texture = data.get('texture')
                if texture and os.path.exists(texture):
                    tex_filename = copy_texture(texture, os.path.dirname(obj_path))
                    if tex_filename:
                        mtl.write(f"map_Kd {tex_filename}\n")
                        # Добавляем базовые свойства, если их нет
                        if 'Kd' not in str(data.get('properties', [])):
                            mtl.write("Kd 0.8 0.8 0.8\n")
                            mtl.write("Ka 0.08 0.08 0.08\n")
                            mtl.write("Ks 0.1 0.1 0.1\n")
                            mtl.write("Ns 10.0\n")

    print(f"✅ MTL сохранен: {mtl_path}")

    # --- Пишем OBJ файл ---
    with open(obj_path, "w", encoding='utf-8') as obj:
        obj.write("# OBJ файл\n")
        obj.write(f"mtllib {mtl_name}\n\n")

        vo = 0  # Смещение вершин
        vto = 0  # Смещение UV координат

        for mesh, mat, tex in meshes:
            if mesh is None:
                continue
                
            # --- Обработка фурнитуры с вложенными материалами ---
            if mat and tex and tex.lower().endswith('.obj'):
                original_obj_path = tex
                original_mtl_path = os.path.splitext(original_obj_path)[0] + ".mtl"
                original_mtl_props = parse_mtl(original_mtl_path)
                original_material_names = list(original_mtl_props.keys())
                obj.write(f"o {mat}\n")
            elif mat:  # --- Стандартная обработка ---
                obj.write(f"usemtl {mat}\n")

            # Вершины
            verts = np.asarray(mesh.vertices)
            for v in verts:
                obj.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            obj.write("\n")

            # Нормали
            if mesh.has_vertex_normals():
                normals = np.asarray(mesh.vertex_normals)
                for n in normals:
                    obj.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
                obj.write("\n")

            # UV координаты - ПРОВЕРЯЕМ ПРАВИЛЬНО
            # В Open3D UV могут храниться в triangle_uvs (для треугольников)
            has_uv = False
            uvs = None
            
            if mesh.has_triangle_uvs():
                uvs = np.asarray(mesh.triangle_uvs)
                has_uv = len(uvs) > 0
            elif hasattr(mesh, 'vertex_uvs') and mesh.vertex_uvs is not None:
                # Некоторые версии Open3D хранят UV в vertex_uvs
                uvs = np.asarray(mesh.vertex_uvs)
                has_uv = len(uvs) > 0
            
            # Проверяем, нужно ли использовать UV
            use_uv = has_uv and (tex is not None or (mat and tex and tex.lower().endswith('.obj')))
            
            if use_uv and uvs is not None:
                for uv_pair in uvs:
                    obj.write(f"vt {uv_pair[0]:.6f} {uv_pair[1]:.6f}\n")
                obj.write("\n")

            # --- Запись полигонов ---
            if mat and tex and tex.lower().endswith('.obj'):
                # Для фурнитуры: записываем полигоны, сгруппированные по материалам
                all_faces = np.asarray(mesh.triangles)
                has_n = mesh.has_vertex_normals()
                has_vt = use_uv
                
                # Проверяем наличие triangle_material_ids
                if not hasattr(mesh, 'triangle_material_ids') or mesh.triangle_material_ids is None:
                    print(f"⚠️ Меш {mat} не содержит triangle_material_ids, используем один материал")
                    faces_by_mat = {0: list(range(len(all_faces)))}
                else:
                    faces_by_mat = defaultdict(list)
                    for i, tri_mat_id in enumerate(np.asarray(mesh.triangle_material_ids)):
                        faces_by_mat[tri_mat_id].append(i)

                for mat_id, face_indices in faces_by_mat.items():
                    if mat_id < len(original_material_names):
                        orig_mat_name = original_material_names[mat_id]
                        new_mat_name = f"{mat}_{orig_mat_name}"
                        obj.write(f"usemtl {new_mat_name}\n")
                    else:
                        obj.write(f"usemtl {mat}\n")
                    
                    for face_idx in face_indices:
                        f = all_faces[face_idx] + 1 + vo
                        if has_vt and has_n:
                            obj.write(f"f {f[0]}/{f[0]}/{f[0]} {f[1]}/{f[1]}/{f[1]} {f[2]}/{f[2]}/{f[2]}\n")
                        elif has_n:
                            obj.write(f"f {f[0]}//{f[0]} {f[1]}//{f[1]} {f[2]}//{f[2]}\n")
                        else:
                            obj.write(f"f {f[0]} {f[1]} {f[2]}\n")
                    obj.write("\n")
            else:
                # Стандартная запись полигонов
                faces = np.asarray(mesh.triangles) + 1 + vo
                has_n = mesh.has_vertex_normals()
                has_vt = use_uv
                
                for fi, f in enumerate(faces):
                    if has_vt and uvs is not None:
                        # Для UV-per-vertex
                        if len(uvs) == len(verts):
                            u1, u2, u3 = f[0], f[1], f[2]
                            if has_n:
                                obj.write(f"f {f[0]}/{u1}/{f[0]} {f[1]}/{u2}/{f[1]} {f[2]}/{u3}/{f[2]}\n")
                            else:
                                obj.write(f"f {f[0]}/{u1} {f[1]}/{u2} {f[2]}/{u3}\n")
                        # Для UV-per-triangle
                        elif len(uvs) == len(faces) * 3:
                            u1, u2, u3 = 3 * fi + 1 + vto, 3 * fi + 2 + vto, 3 * fi + 3 + vto
                            if has_n:
                                obj.write(f"f {f[0]}/{u1}/{f[0]} {f[1]}/{u2}/{f[1]} {f[2]}/{u3}/{f[2]}\n")
                            else:
                                obj.write(f"f {f[0]}/{u1} {f[1]}/{u2} {f[2]}/{u3}\n")
                    else:
                        if has_n:
                            obj.write(f"f {f[0]}//{f[0]} {f[1]}//{f[1]} {f[2]}//{f[2]}\n")
                        else:
                            obj.write(f"f {f[0]} {f[1]} {f[2]}\n")
                obj.write("\n")

            # Обновляем смещения
            vo += len(verts)
            if use_uv and uvs is not None:
                vto += len(uvs)

    print(f"✅ OBJ сохранен: {obj_path}")