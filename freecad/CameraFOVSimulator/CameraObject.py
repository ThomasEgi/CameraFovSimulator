"""Persistent camera object and view provider for CameraFOVSimulator."""

import os

import FreeCAD as App
import FreeCADGui as Gui
import Part

from . import SensorDatabase
from .CameraFOV import fov_degrees, pyramid_shape

ICON = os.path.join(os.path.dirname(__file__), "Resources", "Icons", "camera.svg")

RELEVANT_PROPERTIES = (
    "Manufacturer",
    "SensorModel",
    "SensorSource",
    "SensorWidth",
    "SensorHeight",
    "FocalLength",
    "PyramidDepth",
)


class CameraFOVProxy:
    """Document object that rebuilds a line-only FOV pyramid."""

    Type = "CameraFOVCamera"

    def __init__(self, obj):
        obj.Proxy = self
        self._updating = False
        self._add_properties(obj)

    def _add_properties(self, obj):
        self._updating = True
        try:
            properties = obj.PropertiesList
            manufacturers = SensorDatabase.MANUFACTURERS

            if "Manufacturer" not in properties:
                obj.addProperty(
                    "App::PropertyEnumeration",
                    "Manufacturer",
                    "Sensor",
                    "Sensor manufacturer",
                )
            current_manufacturer = getattr(
                obj, "Manufacturer", SensorDatabase.default_manufacturer()
            )
            if current_manufacturer not in manufacturers:
                current_manufacturer = SensorDatabase.default_manufacturer()
            obj.Manufacturer = list(manufacturers)
            obj.Manufacturer = current_manufacturer

            models = SensorDatabase.sensors_for(current_manufacturer)
            if "SensorModel" not in properties:
                obj.addProperty(
                    "App::PropertyEnumeration",
                    "SensorModel",
                    "Sensor",
                    "Sensor model or part number",
                )
            current_model = getattr(obj, "SensorModel", None)
            if current_model not in models:
                current_model = SensorDatabase.default_model(
                    current_manufacturer
                )
            if models:
                obj.SensorModel = list(models)
                obj.SensorModel = current_model

            if "SensorSource" not in properties:
                obj.addProperty(
                    "App::PropertyEnumeration",
                    "SensorSource",
                    "Sensor",
                    "Catalog sensor or manually entered dimensions",
                )
                obj.SensorSource = ["Catalog", "Custom"]
                obj.SensorSource = "Catalog"
            if "SensorWidth" not in properties:
                obj.addProperty(
                    "App::PropertyLength",
                    "SensorWidth",
                    "Sensor",
                    "Physical sensor width in mm",
                )
            if "SensorHeight" not in properties:
                obj.addProperty(
                    "App::PropertyLength",
                    "SensorHeight",
                    "Sensor",
                    "Physical sensor height in mm",
                )
            if "FocalLength" not in properties:
                obj.addProperty(
                    "App::PropertyLength",
                    "FocalLength",
                    "Optics",
                    "Lens focal length in mm",
                )
                obj.FocalLength = 8.0
            if "PyramidDepth" not in properties:
                obj.addProperty(
                    "App::PropertyLength",
                    "PyramidDepth",
                    "Display",
                    "Length of the drawn FOV pyramid",
                )
                obj.PyramidDepth = 100.0
            if "HorizontalFOV" not in properties:
                obj.addProperty(
                    "App::PropertyAngle",
                    "HorizontalFOV",
                    "Field of View",
                    "Computed horizontal field of view",
                )
            if "VerticalFOV" not in properties:
                obj.addProperty(
                    "App::PropertyAngle",
                    "VerticalFOV",
                    "Field of View",
                    "Computed vertical field of view",
                )

            if getattr(obj, "SensorSource", "Catalog") == "Catalog":
                self._apply_catalog_sensor(obj)
            self._update_editor_modes(obj)
            self._set_read_only_fov(obj)
        finally:
            self._updating = False

    @staticmethod
    def _set_read_only_fov(obj):
        for name in ("HorizontalFOV", "VerticalFOV"):
            try:
                obj.setEditorMode(name, 1)
            except Exception:
                pass

    @staticmethod
    def _update_editor_modes(obj):
        custom = getattr(obj, "SensorSource", "Catalog") == "Custom"
        for name in ("SensorWidth", "SensorHeight"):
            try:
                obj.setEditorMode(name, 0 if custom else 1)
            except Exception:
                pass

    @staticmethod
    def _sync_model_list(obj):
        manufacturer = getattr(obj, "Manufacturer", "")
        models = SensorDatabase.sensors_for(manufacturer)
        current = getattr(obj, "SensorModel", None)
        try:
            obj.SensorModel = list(models)
        except Exception:
            pass
        if not models:
            return
        if current not in models:
            current = SensorDatabase.default_model(manufacturer)
        try:
            obj.SensorModel = current
        except Exception:
            pass

    @staticmethod
    def _apply_catalog_sensor(obj):
        entry = SensorDatabase.sensor(
            getattr(obj, "Manufacturer", ""),
            getattr(obj, "SensorModel", ""),
        )
        if entry is None:
            return
        obj.SensorWidth = entry["width_mm"]
        obj.SensorHeight = entry["height_mm"]

    def onChanged(self, obj, prop):
        if getattr(self, "_updating", False):
            return
        if prop not in RELEVANT_PROPERTIES:
            return

        self._updating = True
        try:
            if prop == "Manufacturer":
                self._sync_model_list(obj)
                if getattr(obj, "SensorSource", "Catalog") == "Catalog":
                    self._apply_catalog_sensor(obj)
            elif prop == "SensorModel":
                if getattr(obj, "SensorSource", "Catalog") == "Catalog":
                    self._apply_catalog_sensor(obj)
            elif prop == "SensorSource":
                self._update_editor_modes(obj)
                if getattr(obj, "SensorSource", "Catalog") == "Catalog":
                    self._apply_catalog_sensor(obj)
        finally:
            self._updating = False
        obj.touch()

    def execute(self, obj):
        width = float(getattr(obj, "SensorWidth", 0.0))
        height = float(getattr(obj, "SensorHeight", 0.0))
        focal = float(getattr(obj, "FocalLength", 0.0))
        depth = float(getattr(obj, "PyramidDepth", 100.0))

        horizontal, vertical = fov_degrees(width, height, focal)
        self._updating = True
        try:
            obj.HorizontalFOV = horizontal
            obj.VerticalFOV = vertical
        finally:
            self._updating = False

        try:
            obj.Shape = pyramid_shape(width, height, focal, depth)
        except Exception:
            obj.Shape = Part.makeCompound([])

    def onDocumentRestored(self, obj):
        self._updating = True
        try:
            self._add_properties(obj)
        finally:
            self._updating = False
        obj.touch()

    def dumps(self):
        return None

    def loads(self, state):
        return None


class ViewProviderCamera:
    """View provider that opens the camera tool on double-click."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def getIcon(self):
        return ICON

    def attach(self, vobj):
        self.Object = vobj.Object
        self._apply_style(vobj)

    @staticmethod
    def _apply_style(vobj):
        try:
            vobj.DisplayMode = "Flat Lines"
            vobj.LineColor = (0.10, 0.72, 1.0)
            vobj.LineWidth = 2.0
            vobj.Visibility = True
        except Exception:
            pass

    def setEdit(self, vobj, mode):
        if mode != 0:
            return False
        from .CameraTaskPanel import CameraTaskPanel

        Gui.Control.showDialog(CameraTaskPanel(camera=vobj.Object))
        return True

    def unsetEdit(self, vobj, mode):
        if mode != 0:
            return False
        Gui.Control.closeDialog()
        return True

    def doubleClicked(self, vobj):
        Gui.ActiveDocument.setEdit(vobj.Object, 0)
        return True

    def setupContextMenu(self, vobj, menu):
        from PySide import QtGui

        edit_action = QtGui.QAction("Edit Camera", menu)
        edit_action.triggered.connect(
            lambda: Gui.ActiveDocument.setEdit(vobj.Object, 0)
        )
        menu.addAction(edit_action)

        activate_action = QtGui.QAction("Activate View", menu)
        activate_action.triggered.connect(
            lambda: _activate_camera_view(vobj.Object)
        )
        menu.addAction(activate_action)

    def onDelete(self, vobj, subelements):
        from .CameraViewSync import manager

        obj = vobj.Object
        manager().deactivate(obj)
        if subelements:
            document = obj.Document
            document_name = document.Name
            object_name = obj.Name

            def remove_camera():
                try:
                    gui_document = Gui.ActiveDocument
                    if gui_document is not None:
                        gui_document.resetEdit()
                except Exception:
                    pass
                document = App.getDocument(document_name)
                if document is not None and document.getObject(object_name) is not None:
                    document.removeObject(object_name)

            try:
                from PySide import QtCore

                QtCore.QTimer.singleShot(0, remove_camera)
            except Exception:
                remove_camera()
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _activate_camera_view(obj):
    from .CameraViewSync import manager

    manager().activate(obj)


def is_camera(obj):
    return getattr(getattr(obj, "Proxy", None), "Type", None) == CameraFOVProxy.Type


def create_camera(document=None):
    document = document or App.ActiveDocument or App.newDocument("CameraFOV")
    obj = document.addObject("Part::FeaturePython", "Camera")
    CameraFOVProxy(obj)
    provider = ViewProviderCamera(obj.ViewObject)
    provider._apply_style(obj.ViewObject)
    obj.Label = "Camera"
    obj.touch()
    document.recompute()
    return obj


def add_to_container(container, obj):
    if container is None or obj is None:
        return
    try:
        if getattr(container, "TypeId", "") == "App::Part":
            container.addObject(obj)
            return
    except Exception:
        pass
    try:
        if hasattr(container, "Group"):
            container.Group = list(container.Group) + [obj]
    except Exception:
        pass
