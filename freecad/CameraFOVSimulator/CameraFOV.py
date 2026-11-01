"""Field-of-view calculations and line-only FOV pyramid geometry."""

import math

import FreeCAD as App
import Part


def fov_angles(sensor_width_mm, sensor_height_mm, focal_length_mm):
    """Return horizontal and vertical field of view in radians."""
    width = float(sensor_width_mm)
    height = float(sensor_height_mm)
    focal = float(focal_length_mm)
    if width <= 0.0 or height <= 0.0 or focal <= 0.0:
        return 0.0, 0.0
    horizontal = 2.0 * math.atan(width / (2.0 * focal))
    vertical = 2.0 * math.atan(height / (2.0 * focal))
    return horizontal, vertical


def fov_degrees(sensor_width_mm, sensor_height_mm, focal_length_mm):
    """Return horizontal and vertical field of view in degrees."""
    horizontal, vertical = fov_angles(
        sensor_width_mm, sensor_height_mm, focal_length_mm
    )
    return math.degrees(horizontal), math.degrees(vertical)


def pyramid_shape(
    sensor_width_mm,
    sensor_height_mm,
    focal_length_mm,
    depth_mm=100.0,
):
    """Build a line-only rectangular FOV pyramid with the apex at the origin."""
    horizontal, vertical = fov_angles(
        sensor_width_mm, sensor_height_mm, focal_length_mm
    )
    depth = float(depth_mm)
    if horizontal <= 0.0 or vertical <= 0.0 or depth <= 0.0:
        return Part.makeCompound([])

    half_width = depth * math.tan(horizontal / 2.0)
    half_height = depth * math.tan(vertical / 2.0)
    if not all(
        math.isfinite(value)
        for value in (half_width, half_height)
    ):
        return Part.makeCompound([])

    apex = App.Vector(0.0, 0.0, 0.0)
    corners = (
        App.Vector(-half_width, -half_height, depth),
        App.Vector(half_width, -half_height, depth),
        App.Vector(half_width, half_height, depth),
        App.Vector(-half_width, half_height, depth),
    )

    edges = [Part.makeLine(apex, corner) for corner in corners]
    edges.extend(
        Part.makeLine(corners[index], corners[(index + 1) % 4])
        for index in range(4)
    )
    return Part.makeCompound(edges)


def view_vertical_fov(horizontal, vertical, viewport_aspect, margin=1.05):
    """Vertical view FOV that contains both sensor FOV axes plus margin."""
    if horizontal <= 0.0 or vertical <= 0.0:
        return 0.0
    aspect = float(viewport_aspect)
    if aspect <= 0.0:
        aspect = 1.0
    horizontal_fit = 2.0 * math.atan(math.tan(horizontal / 2.0) / aspect)
    return min(max(vertical, horizontal_fit) * float(margin), math.pi * 0.98)
