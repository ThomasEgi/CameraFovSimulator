"""Task panel for editing a CameraFOVSimulator camera object."""

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from . import SensorDatabase
from .CameraFOV import fov_degrees
from .CameraViewSync import manager


class CameraTaskPanel:
    """Edit the sensor, lens and active 3D view of a camera."""

    def __init__(self, camera=None):
        self.camera = camera
        self._updating = False
        self._manager = manager()

        self.form = QtGui.QWidget()
        self.form.setWindowTitle("Camera Settings")

        layout = QtGui.QVBoxLayout(self.form)

        sensor_group = QtGui.QGroupBox("Sensor")
        sensor_layout = QtGui.QFormLayout(sensor_group)
        self.manufacturer_combo = QtGui.QComboBox()
        self.model_combo = QtGui.QComboBox()
        self.custom_checkbox = QtGui.QCheckBox("Custom sensor dimensions")
        self.width_spin = QtGui.QDoubleSpinBox()
        self.width_spin.setRange(0.001, 1000.0)
        self.width_spin.setDecimals(3)
        self.width_spin.setSingleStep(0.1)
        self.width_spin.setSuffix(" mm")
        self.height_spin = QtGui.QDoubleSpinBox()
        self.height_spin.setRange(0.001, 1000.0)
        self.height_spin.setDecimals(3)
        self.height_spin.setSingleStep(0.1)
        self.height_spin.setSuffix(" mm")
        self.info_label = QtGui.QLabel("")
        self.info_label.setWordWrap(True)

        sensor_layout.addRow("Manufacturer:", self.manufacturer_combo)
        sensor_layout.addRow("Sensor model:", self.model_combo)
        sensor_layout.addRow("", self.custom_checkbox)
        sensor_layout.addRow("Sensor X:", self.width_spin)
        sensor_layout.addRow("Sensor Y:", self.height_spin)
        sensor_layout.addRow("Data:", self.info_label)
        layout.addWidget(sensor_group)

        optics_group = QtGui.QGroupBox("Optics")
        optics_layout = QtGui.QFormLayout(optics_group)
        self.focal_spin = QtGui.QDoubleSpinBox()
        self.focal_spin.setRange(0.01, 10000.0)
        self.focal_spin.setDecimals(3)
        self.focal_spin.setSingleStep(0.5)
        self.focal_spin.setSuffix(" mm")
        self.fov_label = QtGui.QLabel("")
        self.fov_label.setWordWrap(True)
        optics_layout.addRow("Focal length:", self.focal_spin)
        optics_layout.addRow("Field of view:", self.fov_label)
        layout.addWidget(optics_group)

        view_group = QtGui.QGroupBox("3D View")
        view_layout = QtGui.QVBoxLayout(view_group)
        self.activate_button = QtGui.QPushButton("Activate View")
        self.activate_button.setCheckable(True)
        self.view_hint = QtGui.QLabel(
            "While active, changes to the camera and its placement update "
            "the 3D view. Rotating, panning or zooming the view manually "
            "deactivates it."
        )
        self.view_hint.setWordWrap(True)
        view_layout.addWidget(self.activate_button)
        view_layout.addWidget(self.view_hint)
        layout.addWidget(view_group)

        self.status_label = QtGui.QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self._apply_timer = QtCore.QTimer(self.form)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(100)
        self._apply_timer.timeout.connect(self._apply_values)

        self.manufacturer_combo.currentIndexChanged.connect(
            self._on_manufacturer_changed
        )
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self.custom_checkbox.toggled.connect(self._on_custom_toggled)
        self.width_spin.valueChanged.connect(self._on_value_changed)
        self.height_spin.valueChanged.connect(self._on_value_changed)
        self.focal_spin.valueChanged.connect(self._on_value_changed)
        self.activate_button.toggled.connect(self._on_activate_toggled)
        self._manager_connected = True
        self._manager.stateChanged.connect(self._on_view_state_changed)
        self.form.destroyed.connect(self._on_destroyed)

        self._load()
        self._sync_view_button()

    def _valid_camera(self):
        try:
            return self.camera is not None and self.camera.isValid()
        except Exception:
            return False

    def _load(self):
        if not self._valid_camera():
            self.status_label.setText("No valid camera object.")
            return

        self._updating = True
        try:
            manufacturer = getattr(self.camera, "Manufacturer", "")
            if manufacturer not in SensorDatabase.MANUFACTURERS:
                manufacturer = SensorDatabase.default_manufacturer()
            self._populate_manufacturers(manufacturer)

            model = getattr(self.camera, "SensorModel", "")
            self._populate_models(manufacturer, model)

            custom = getattr(self.camera, "SensorSource", "Catalog") == "Custom"
            self.custom_checkbox.setChecked(custom)
            self.width_spin.setValue(float(getattr(self.camera, "SensorWidth", 0.0)))
            self.height_spin.setValue(
                float(getattr(self.camera, "SensorHeight", 0.0))
            )
            self.focal_spin.setValue(
                float(getattr(self.camera, "FocalLength", 8.0))
            )
        finally:
            self._updating = False

        self._update_enabled()
        self._update_info()

    def _populate_manufacturers(self, selected):
        self.manufacturer_combo.clear()
        self.manufacturer_combo.addItems(list(SensorDatabase.MANUFACTURERS))
        index = self.manufacturer_combo.findText(selected)
        self.manufacturer_combo.setCurrentIndex(index if index >= 0 else 0)

    def _populate_models(self, manufacturer, selected):
        models = list(SensorDatabase.sensors_for(manufacturer))
        self.model_combo.clear()
        for model in models:
            self.model_combo.addItem(
                SensorDatabase.sensor_label(manufacturer, model), model
            )
        if not models:
            return
        index = self.model_combo.findData(selected)
        if index < 0:
            selected = SensorDatabase.default_model(manufacturer)
            index = self.model_combo.findData(selected)
        self.model_combo.setCurrentIndex(index if index >= 0 else 0)

    def _on_manufacturer_changed(self, index):
        if self._updating or not self._valid_camera():
            return
        manufacturer = self.manufacturer_combo.currentText()
        if not manufacturer:
            return

        self._updating = True
        try:
            self.camera.Manufacturer = manufacturer
            model = getattr(self.camera, "SensorModel", "")
            models = SensorDatabase.sensors_for(manufacturer)
            if model not in models:
                model = SensorDatabase.default_model(manufacturer)
                self.camera.SensorModel = model
            self._populate_models(manufacturer, model)
            if getattr(self.camera, "SensorSource", "Catalog") == "Catalog":
                self._apply_catalog_entry(manufacturer, model)
        finally:
            self._updating = False
        self._recompute()
        self._update_info()
        self._manager.refresh(self.camera)

    def _on_model_changed(self, index):
        if self._updating or not self._valid_camera():
            return
        manufacturer = self.manufacturer_combo.currentText()
        model = self.model_combo.currentData()
        if not manufacturer or not model:
            return

        self.camera.SensorModel = model
        if getattr(self.camera, "SensorSource", "Catalog") == "Catalog":
            self._apply_catalog_entry(manufacturer, model)
            self._recompute()
            self._manager.refresh(self.camera)
        self._update_info()

    def _apply_catalog_entry(self, manufacturer, model):
        entry = SensorDatabase.sensor(manufacturer, model)
        if entry is None:
            return
        self.camera.SensorWidth = entry["width_mm"]
        self.camera.SensorHeight = entry["height_mm"]
        self._updating = True
        try:
            self.width_spin.setValue(entry["width_mm"])
            self.height_spin.setValue(entry["height_mm"])
        finally:
            self._updating = False

    def _on_custom_toggled(self, checked):
        if self._updating or not self._valid_camera():
            return
        self._updating = True
        try:
            self.camera.SensorSource = "Custom" if checked else "Catalog"
            if not checked:
                manufacturer = self.manufacturer_combo.currentText()
                model = self.model_combo.currentData()
                self._apply_catalog_entry(manufacturer, model)
        finally:
            self._updating = False
        self._update_enabled()
        self._recompute()
        self._update_info()
        self._manager.refresh(self.camera)

    def _on_value_changed(self, value):
        self._update_info()
        if not self._updating:
            self._apply_timer.start()

    def _apply_values(self):
        if not self._valid_camera():
            return
        self.camera.SensorWidth = self.width_spin.value()
        self.camera.SensorHeight = self.height_spin.value()
        self.camera.FocalLength = self.focal_spin.value()
        self._recompute()
        self._update_info()
        self._manager.refresh(self.camera)

    def _recompute(self):
        if not self._valid_camera():
            return
        try:
            self.camera.touch()
            self.camera.Document.recompute()
        except Exception as error:
            self.status_label.setText(str(error))

    def _update_enabled(self):
        custom = self.custom_checkbox.isChecked()
        self.width_spin.setEnabled(custom)
        self.height_spin.setEnabled(custom)
        self.manufacturer_combo.setEnabled(not custom)
        self.model_combo.setEnabled(not custom)

    def _update_info(self):
        custom = self.custom_checkbox.isChecked()
        if custom:
            self.info_label.setText("Custom sensor dimensions")
        else:
            entry = SensorDatabase.sensor(
                self.manufacturer_combo.currentText(),
                self.model_combo.currentData(),
            )
            if entry is None:
                self.info_label.setText("No catalog data")
            else:
                resolution = entry["resolution"]
                self.info_label.setText(
                    f"Resolution: {resolution[0]} x {resolution[1]} px | "
                    f"Pixel size: {entry['pixel_size_um']:g} µm"
                )

        horizontal, vertical = fov_degrees(
            self.width_spin.value(),
            self.height_spin.value(),
            self.focal_spin.value(),
        )
        if horizontal > 0.0 and vertical > 0.0:
            self.fov_label.setText(
                f"H: {horizontal:.2f}° | V: {vertical:.2f}°"
            )
        else:
            self.fov_label.setText("-")

    def _on_activate_toggled(self, checked):
        if self._updating:
            return
        if not self._valid_camera():
            self._sync_view_button()
            return

        if checked:
            if self._manager.activate(self.camera):
                self.status_label.clear()
            else:
                self.status_label.setText(
                    "Could not activate the 3D view. Ensure a 3D view is open."
                )
        else:
            self._manager.deactivate(self.camera)
            self.status_label.clear()
        self._sync_view_button()

    def _on_view_state_changed(self, active):
        self._sync_view_button()

    def _sync_view_button(self):
        active = self._manager.is_active(self.camera)
        self.activate_button.blockSignals(True)
        self.activate_button.setChecked(active)
        self.activate_button.setText(
            "Deactivate View" if active else "Activate View"
        )
        self.activate_button.blockSignals(False)

    def _on_destroyed(self, *args):
        self._apply_timer.stop()
        if self._manager_connected:
            self._manager_connected = False
            try:
                self._manager.stateChanged.disconnect(self._on_view_state_changed)
            except Exception:
                pass

    def getStandardButtons(self):
        return QtGui.QDialogButtonBox.Close

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True

    def _flush_pending(self):
        if self._apply_timer.isActive():
            self._apply_timer.stop()
            self._apply_values()

    def _end_edit_mode(self):
        try:
            gui_document = Gui.ActiveDocument
            if gui_document is None:
                return
            in_edit = gui_document.getInEdit()
            if in_edit is not None and getattr(in_edit, "Object", None) is self.camera:
                gui_document.resetEdit()
        except Exception:
            pass

    def accept(self):
        self._flush_pending()
        self._on_destroyed()
        Gui.Control.closeDialog()
        self._end_edit_mode()

    def reject(self):
        self._flush_pending()
        self._on_destroyed()
        Gui.Control.closeDialog()
        self._end_edit_mode()
