"""Workbench definition for CameraFOVSimulator."""

import os

import FreeCADGui

ICON_DIR = os.path.join(os.path.dirname(__file__), "Resources", "Icons")


class CameraFOVSimulatorWorkbench(FreeCADGui.Workbench):
    """Camera field-of-view planning workbench."""

    MenuText = "Camera FOV Simulator"
    ToolTip = "Create cameras and visualize their field of view"
    Icon = os.path.join(ICON_DIR, "camera.svg")

    def __init__(self):
        self._initialized = False

    def Initialize(self):
        if self._initialized:
            return
        import freecad.CameraFOVSimulator.Commands  # noqa: F401

        commands = [
            "CameraFOVSimulator_CreateCamera",
            "CameraFOVSimulator_EditCamera",
        ]
        self.appendToolbar("Camera", commands)
        self.appendMenu("Camera FOV Simulator", commands)
        self._initialized = True

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(CameraFOVSimulatorWorkbench())
