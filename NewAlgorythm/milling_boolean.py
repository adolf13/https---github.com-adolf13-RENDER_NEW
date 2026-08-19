"""Robust Boolean subtraction of analytic cutter sweeps from a solid door leaf."""

from __future__ import annotations

from typing import Iterable

import manifold3d as manifold
import numpy as np
import open3d as o3d


def _assign_planar_uv(mesh: o3d.geometry.TriangleMesh, width: float, height: float) -> None:
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)
    uvs = []
    for triangle in triangles:
        for vertex_index in triangle:
            x, y, _ = vertices[vertex_index]
            uvs.append((x / width, y / height))
    mesh.triangle_uvs = o3d.utility.Vector2dVector(np.asarray(uvs, dtype=np.float64))


def _as_manifold(mesh: o3d.geometry.TriangleMesh, label: str) -> manifold.Manifold:
    if not mesh.is_watertight():
        raise ValueError(f"{label} is not watertight")
    vertices = np.ascontiguousarray(np.asarray(mesh.vertices), dtype=np.float32)
    triangles = np.ascontiguousarray(np.asarray(mesh.triangles), dtype=np.uint32)
    result = manifold.Manifold(manifold.Mesh(vertices, triangles))
    if result.is_empty() or result.status() != manifold.Error.NoError:
        raise ValueError(f"{label} cannot be converted to a valid manifold: {result.status()}")
    return result


def _from_manifold(source: manifold.Manifold) -> o3d.geometry.TriangleMesh:
    mesh_data = source.to_mesh()
    result = o3d.geometry.TriangleMesh()
    result.vertices = o3d.utility.Vector3dVector(
        np.asarray(mesh_data.vert_properties[:, :3], dtype=np.float64).copy()
    )
    result.triangles = o3d.utility.Vector3iVector(
        np.asarray(mesh_data.tri_verts, dtype=np.int32).copy()
    )
    result.compute_vertex_normals()
    return result


def subtract_sweeps_from_door(
    door_width_m: float,
    door_height_m: float,
    door_thickness_m: float,
    sweep_meshes: Iterable[o3d.geometry.TriangleMesh],
) -> o3d.geometry.TriangleMesh:
    """Return one solid door mesh with the union of all cutter sweeps subtracted."""
    sweeps = list(sweep_meshes)
    if not sweeps:
        raise ValueError("No cutter sweep meshes were supplied")
    cutter_union = manifold.Manifold.batch_boolean(
        [_as_manifold(mesh, f"Cutter sweep {index}") for index, mesh in enumerate(sweeps, 1)],
        manifold.OpType.Add,
    )
    body = manifold.Manifold.cube((door_width_m, door_height_m, door_thickness_m))
    result_manifold = body - cutter_union
    if result_manifold.is_empty() or result_manifold.status() != manifold.Error.NoError:
        raise RuntimeError(f"Milling Boolean failed: {result_manifold.status()}")

    result = _from_manifold(result_manifold)
    result.compute_vertex_normals()
    _assign_planar_uv(result, door_width_m, door_height_m)
    return result
