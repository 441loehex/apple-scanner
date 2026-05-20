"""Point cloud and mesh loading from PLY, OBJ, GLB formats."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def load_ply(path: Path) -> np.ndarray:
    """
    Returns (N, 3) float32 XYZ, or (N, 6) float32 XYZ + RGB if the file has
    per-vertex colour (standard Polycam / Scaniverse coloured PLY exports).
    """
    try:
        from plyfile import PlyData

        ply = PlyData.read(str(path))
        vertex = ply["vertex"]
        names = vertex.data.dtype.names

        x = np.array(vertex["x"], dtype=np.float32)
        y = np.array(vertex["y"], dtype=np.float32)
        z = np.array(vertex["z"], dtype=np.float32)
        xyz = np.column_stack([x, y, z])

        # Read per-vertex colour when present (Polycam exports red/green/blue uchar)
        if "red" in names and "green" in names and "blue" in names:
            r = np.array(vertex["red"], dtype=np.float32)
            g = np.array(vertex["green"], dtype=np.float32)
            b = np.array(vertex["blue"], dtype=np.float32)
            # Some exporters write colours as 0-1 floats; convert to 0-255
            if r.max() <= 1.0:
                r, g, b = r * 255.0, g * 255.0, b * 255.0
            logger.info("PLY has per-vertex colour — using coloured rendering")
            return np.column_stack([xyz, r, g, b])

        return xyz

    except Exception as e:
        logger.warning("plyfile load failed (%s), trying binary fallback: %s", path.name, e)
        return _load_ply_fallback(path)


def _load_ply_fallback(path: Path) -> np.ndarray:
    """Minimal binary PLY parser fallback (XYZ only)."""
    data = path.read_bytes()
    header_end = data.find(b"end_header\n")
    if header_end == -1:
        raise ValueError(f"Invalid PLY file: {path}")
    header = data[: header_end].decode("ascii", errors="replace")
    body = data[header_end + len("end_header\n"):]

    vertex_count = 0
    for line in header.splitlines():
        if line.startswith("element vertex"):
            vertex_count = int(line.split()[-1])
            break

    if vertex_count == 0:
        return np.zeros((0, 3), dtype=np.float32)

    try:
        arr = np.frombuffer(body, dtype=np.float32)
        n_floats_per_vertex = len(arr) // vertex_count
        if n_floats_per_vertex < 3:
            raise ValueError("Not enough floats per vertex")
        arr = arr.reshape(vertex_count, n_floats_per_vertex)
        return arr[:, :3].copy()
    except Exception as e:
        raise ValueError(f"PLY binary fallback failed for {path}: {e}") from e


def load_mesh(path: Path) -> np.ndarray:
    """Load OBJ or GLB using trimesh. Returns (N, 3) float32 vertex array."""
    try:
        import trimesh

        mesh = trimesh.load(str(path), force="mesh")
        if hasattr(mesh, "vertices"):
            return np.array(mesh.vertices, dtype=np.float32)
        vertices = []
        for geom in mesh.geometry.values():  # type: ignore[attr-defined]
            vertices.append(np.array(geom.vertices, dtype=np.float32))
        if vertices:
            return np.vstack(vertices)
        return np.zeros((0, 3), dtype=np.float32)
    except Exception as e:
        raise ValueError(f"Mesh load failed for {path}: {e}") from e


def load_polycam_raw_zip(
    zip_path: Path,
    min_confidence: int = 54,
    max_depth_m: float = 5.0,
    subsample: int = 1,
) -> np.ndarray:
    """
    Reconstruct colored (N, 6) float32 point cloud from a Polycam 'Raw' export ZIP.

    Depth scale: 1 uint16 unit = 1 mm (verified from center_depth field).
    Confidence thresholds: 0=none, 54=medium, 255=high.
    Returns (N, 6) array: [X_world, Y_world, Z_world, R, G, B] in world coordinates.
    R/G/B are float32 values in [0, 255].
    """
    import io
    import json
    import zipfile

    zf = zipfile.ZipFile(str(zip_path))
    nameset = set(zf.namelist())

    cam_files = sorted(
        [f for f in nameset if f.startswith("keyframes/cameras/") and f.endswith(".json")]
    )
    if not cam_files:
        raise ValueError(f"No camera files found in {zip_path.name}. Is this a Polycam Raw export?")

    align_mat = None
    if "mesh_info.json" in nameset:
        mi = json.loads(zf.read("mesh_info.json"))
        if "alignmentTransform" in mi:
            align_mat = np.array(
                mi["alignmentTransform"], dtype=np.float64
            ).reshape(4, 4, order="F")

    all_points: list[np.ndarray] = []
    all_colors: list[np.ndarray] = []

    for idx, cam_file in enumerate(cam_files):
        if subsample > 1 and idx % subsample != 0:
            continue

        ts = cam_file.split("/")[-1].replace(".json", "")
        depth_file = f"keyframes/depth/{ts}.png"
        image_file = f"keyframes/images/{ts}.jpg"
        conf_file = f"keyframes/confidence/{ts}.png"

        if depth_file not in nameset or image_file not in nameset:
            continue

        cam = json.loads(zf.read(cam_file))

        fx_rgb = float(cam["fx"])
        fy_rgb = float(cam["fy"])
        cx_rgb = float(cam["cx"])
        cy_rgb = float(cam["cy"])
        rgb_w = int(cam.get("width", 1024))
        rgb_h = int(cam.get("height", 768))

        from PIL import Image  # deferred import
        depth_arr = np.array(Image.open(io.BytesIO(zf.read(depth_file))), dtype=np.float32)
        d_h, d_w = depth_arr.shape[:2]

        sx = d_w / rgb_w
        sy = d_h / rgb_h
        fx = fx_rgb * sx
        fy = fy_rgb * sy
        cx_d = cx_rgb * sx
        cy_d = cy_rgb * sy

        if conf_file in nameset:
            conf_arr = np.array(Image.open(io.BytesIO(zf.read(conf_file))), dtype=np.uint8)
        else:
            conf_arr = np.full((d_h, d_w), 255, dtype=np.uint8)

        depth_m = depth_arr / 1000.0  # mm → metres
        valid = (conf_arr >= min_confidence) & (depth_m > 0.05) & (depth_m < max_depth_m)

        v_idx, u_idx = np.where(valid)
        if len(v_idx) == 0:
            continue

        d = depth_m[v_idx, u_idx]

        x_cam = (u_idx.astype(np.float64) - cx_d) * d / fx
        y_cam = (v_idx.astype(np.float64) - cy_d) * d / fy
        z_cam = d.astype(np.float64)

        T = np.array(
            [
                [cam["t_00"], cam["t_01"], cam["t_02"], cam["t_03"]],
                [cam["t_10"], cam["t_11"], cam["t_12"], cam["t_13"]],
                [cam["t_20"], cam["t_21"], cam["t_22"], cam["t_23"]],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

        pts_cam = np.stack([x_cam, y_cam, z_cam, np.ones_like(z_cam)], axis=1)  # N×4
        pts_world = (T @ pts_cam.T).T[:, :3]  # N×3

        if align_mat is not None:
            pts_h = np.column_stack([pts_world, np.ones(len(pts_world))])
            pts_world = (align_mat @ pts_h.T).T[:, :3]

        rgb_img = np.array(Image.open(io.BytesIO(zf.read(image_file))))
        rgb_u = np.clip((u_idx / sx).astype(np.int32), 0, rgb_w - 1)
        rgb_v = np.clip((v_idx / sy).astype(np.int32), 0, rgb_h - 1)
        colors = rgb_img[rgb_v, rgb_u].astype(np.float32)  # N×3

        all_points.append(pts_world.astype(np.float32))
        all_colors.append(colors)

    if not all_points:
        return np.zeros((0, 6), dtype=np.float32)

    points = np.vstack(all_points)
    colors = np.vstack(all_colors)
    return np.column_stack([points, colors]).astype(np.float32)


def load_scan(path: Path) -> np.ndarray:
    """Auto-detect format and load point cloud. Returns (N, 3) or (N, 6) float32."""
    suffix = path.suffix.lower()
    if suffix == ".zip":
        return load_polycam_raw_zip(path)
    elif suffix == ".ply":
        return load_ply(path)
    elif suffix in (".obj", ".glb", ".gltf"):
        return load_mesh(path)
    elif suffix in (".usdz", ".usd"):
        logger.warning("USDZ/USD loading not supported — returning empty cloud.")
        return np.zeros((0, 3), dtype=np.float32)
    elif suffix in (".las", ".laz"):
        logger.warning("LAS preview unavailable — install laspy. Returning empty cloud.")
        return np.zeros((0, 3), dtype=np.float32)
    else:
        raise ValueError(f"Unsupported scan format: {suffix}")
