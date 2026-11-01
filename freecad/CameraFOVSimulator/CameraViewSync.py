"""Keep the FreeCAD 3D view aligned with the camera being edited."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from pivy import coin
from PySide import QtCore

from .CameraFOV import fov_angles, view_vertical_fov

FOV_MARGIN = 1.05
POLL_INTERVAL_MS = 120
POSITION_TOLERANCE = 1e-4
ANGLE_TOLERANCE = 1e-5
QUATERNION_TOLERANCE = 1e-6


class CameraViewSync(QtCore.QObject):
    """Singleton manager for activating and tracking the camera view."""

    stateChanged = QtCore.Signal(bool)

    def __init__(self):
        super().__init__()
        self._document_name = None
        self._object_name = None
        self._active = False
        self._target = None
        self._expected = None
        self._aspect = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def is_active(self, obj=None):
        if not self._active:
            return False
        if obj is None:
            return True
        document = getattr(obj, "Document", None)
        return (
            document is not None
            and document.Name == self._document_name
            and obj.Name == self._object_name
        )

    def activate(self, obj):
        if obj is None:
            return False
        document = getattr(obj, "Document", None)
        if document is None:
            return False

        if self._active:
            self.deactivate()

        self._document_name = document.Name
        self._object_name = obj.Name
        self._active = True
        self._target = None
        self._expected = None
        self._aspect = None

        if not self._apply():
            self._clear()
            self.stateChanged.emit(False)
            return False

        self._timer.start()
        self.stateChanged.emit(True)
        return True

    def deactivate(self, obj=None):
        if obj is not None and not self.is_active(obj):
            return
        was_active = self._active
        self._timer.stop()
        self._clear()
        if was_active:
            self.stateChanged.emit(False)

    def refresh(self, obj=None):
        if not self._active:
            return
        if obj is not None and not self.is_active(obj):
            return
        gui_document = Gui.ActiveDocument
        view = gui_document.ActiveView if gui_document is not None else None
        if view is None or not self._view_matches_expected(view):
            self.deactivate()
            return
        self._apply()

    def _clear(self):
        self._active = False
        self._document_name = None
        self._object_name = None
        self._target = None
        self._expected = None
        self._aspect = None

    def _object(self):
        if not self._document_name or not self._object_name:
            return None
        document = App.getDocument(self._document_name)
        if document is None:
            return None
        return document.getObject(self._object_name)

    def _compute_target(self, obj):
        try:
            placement = obj.getGlobalPlacement()
        except Exception:
            return None
        rotation = placement.Rotation
        up = rotation.multVec(App.Vector(0.0, 1.0, 0.0))
        forward = rotation.multVec(App.Vector(0.0, 0.0, 1.0))
        backward = -forward
        right = up.cross(backward)
        if right.Length < 1e-9:
            right = App.Vector(1.0, 0.0, 0.0)
        else:
            right.normalize()

        horizontal, vertical = fov_angles(
            float(getattr(obj, "SensorWidth", 0.0)),
            float(getattr(obj, "SensorHeight", 0.0)),
            float(getattr(obj, "FocalLength", 0.0)),
        )
        if horizontal <= 0.0 or vertical <= 0.0:
            return None

        try:
            quaternion = App.Rotation(right, up, backward, "ZXY").Q
        except Exception:
            quaternion = App.Rotation(right, up, backward).Q

        return {
            "position": App.Vector(placement.Base),
            "quaternion": tuple(quaternion),
            "horizontal": horizontal,
            "vertical": vertical,
        }

    @staticmethod
    def _same_target(first, second):
        if first is None or second is None:
            return False
        if (
            first["position"] - second["position"]
        ).Length > POSITION_TOLERANCE:
            return False
        if (
            abs(abs(_quaternion_dot(first["quaternion"], second["quaternion"])) - 1.0)
            > QUATERNION_TOLERANCE
        ):
            return False
        if abs(first["horizontal"] - second["horizontal"]) > ANGLE_TOLERANCE:
            return False
        if abs(first["vertical"] - second["vertical"]) > ANGLE_TOLERANCE:
            return False
        return True

    @staticmethod
    def _viewport_aspect(view):
        try:
            widget = view.graphicsView()
            if widget is not None and widget.height() > 0:
                return float(widget.width()) / float(widget.height())
        except Exception:
            pass
        try:
            return float(view.getCameraNode().aspectRatio.getValue())
        except Exception:
            return 1.0

    def _apply(self):
        if not getattr(App, "GuiUp", False):
            return False
        obj = self._object()
        if obj is None:
            return False
        try:
            if not obj.isValid():
                return False
        except Exception:
            return False

        target = self._compute_target(obj)
        if target is None:
            return False

        active_document = App.ActiveDocument
        if (
            active_document is None
            or active_document.Name != self._document_name
        ):
            return False
        gui_document = Gui.ActiveDocument
        if gui_document is None:
            return False
        view = gui_document.ActiveView
        if view is None:
            return False

        try:
            if str(view.getCameraType()).lower() != "perspective":
                view.setCameraType("Perspective")
        except Exception:
            return False

        try:
            camera = view.getCameraNode()
        except Exception:
            return False
        if not isinstance(camera, coin.SoPerspectiveCamera):
            return False

        aspect = self._viewport_aspect(view)
        if aspect <= 0.0:
            aspect = 1.0
        height_angle = view_vertical_fov(
            target["horizontal"],
            target["vertical"],
            aspect,
            FOV_MARGIN,
        )
        if height_angle <= 0.0:
            return False

        position = target["position"]
        quaternion = target["quaternion"]
        try:
            camera.position.setValue(position.x, position.y, position.z)
            camera.orientation.setValue(
                coin.SbRotation(
                    quaternion[0],
                    quaternion[1],
                    quaternion[2],
                    quaternion[3],
                )
            )
            camera.heightAngle.setValue(height_angle)
            camera.aspectRatio.setValue(aspect)
            camera.nearDistance.setValue(0.001)
            camera.farDistance.setValue(1.0e6)
            view.redraw()
        except Exception:
            return False

        self._target = target
        self._aspect = aspect
        self._expected = {
            "position": (position.x, position.y, position.z),
            "quaternion": tuple(camera.orientation.getValue().getValue()),
            "height_angle": float(camera.heightAngle.getValue()),
        }
        return True

    def _poll(self):
        if not self._active:
            return
        obj = self._object()
        if obj is None:
            self.deactivate()
            return

        target = self._compute_target(obj)
        if target is None:
            self.deactivate()
            return

        active_document = App.ActiveDocument
        if (
            active_document is None
            or active_document.Name != self._document_name
        ):
            self.deactivate()
            return

        gui_document = Gui.ActiveDocument
        view = gui_document.ActiveView if gui_document is not None else None
        if view is None:
            self.deactivate()
            return

        aspect = self._viewport_aspect(view)
        if (
            not self._same_target(target, self._target)
            or self._aspect is None
            or abs(aspect - self._aspect) > 1e-3
        ):
            if not self._apply():
                self.deactivate()
            return

        if not self._view_matches_expected(view):
            self.deactivate()

    def _view_matches_expected(self, view):
        expected = self._expected
        if expected is None:
            return False
        try:
            camera = view.getCameraNode()
        except Exception:
            return False
        if not isinstance(camera, coin.SoPerspectiveCamera):
            return False

        position = camera.position.getValue()
        if _distance(position, expected["position"]) > POSITION_TOLERANCE:
            return False

        quaternion = camera.orientation.getValue().getValue()
        if (
            abs(abs(_quaternion_dot(quaternion, expected["quaternion"])) - 1.0)
            > QUATERNION_TOLERANCE
        ):
            return False

        height_angle = float(camera.heightAngle.getValue())
        if abs(height_angle - expected["height_angle"]) > ANGLE_TOLERANCE:
            return False
        return True


def _distance(first, second):
    return math.sqrt(
        (float(first[0]) - float(second[0])) ** 2
        + (float(first[1]) - float(second[1])) ** 2
        + (float(first[2]) - float(second[2])) ** 2
    )


def _quaternion_dot(first, second):
    return (
        float(first[0]) * float(second[0])
        + float(first[1]) * float(second[1])
        + float(first[2]) * float(second[2])
        + float(first[3]) * float(second[3])
    )


_manager = None


def manager():
    global _manager
    if _manager is None:
        _manager = CameraViewSync()
    return _manager
