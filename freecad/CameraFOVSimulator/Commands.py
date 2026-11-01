"""FreeCAD commands for CameraFOVSimulator."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from .CameraObject import add_to_container, create_camera, is_camera

ICON = os.path.join(os.path.dirname(__file__), "Resources", "Icons", "camera.svg")


def _selected_camera():
    selection = Gui.Selection.getSelection()
    if len(selection) != 1:
        return None
    obj = selection[0]
    return obj if is_camera(obj) else None


class CreateCameraCommand:
    def GetResources(self):
        return {
            "Pixmap": ICON,
            "MenuText": "Create Camera",
            "ToolTip": "Create a camera object with a line-only FOV pyramid",
        }

    def Activated(self):
        try:
            document = App.ActiveDocument or App.newDocument("CameraFOV")
            selection = Gui.Selection.getSelection()
            container = (
                selection[0]
                if len(selection) == 1
                and getattr(selection[0], "TypeId", "") == "App::Part"
                else None
            )
            camera = create_camera(document)
            if container is not None:
                add_to_container(container, camera)
                document.recompute()
            Gui.ActiveDocument.setEdit(camera, 0)
        except Exception as error:
            QtGui.QMessageBox.critical(None, "Camera FOV Simulator", str(error))

    def IsActive(self):
        return True


class EditCameraCommand:
    def GetResources(self):
        return {
            "Pixmap": ICON,
            "MenuText": "Edit Camera",
            "ToolTip": "Open the camera settings for the selected camera",
        }

    def Activated(self):
        camera = _selected_camera()
        if camera is None:
            return
        try:
            Gui.ActiveDocument.setEdit(camera, 0)
        except Exception as error:
            QtGui.QMessageBox.critical(None, "Camera FOV Simulator", str(error))

    def IsActive(self):
        return _selected_camera() is not None


Gui.addCommand("CameraFOVSimulator_CreateCamera", CreateCameraCommand())
Gui.addCommand("CameraFOVSimulator_EditCamera", EditCameraCommand())
