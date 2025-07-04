#! /usr/bin/env python3

import sys
import os

# Set QT_API for picamera2 to PyQt6 BEFORE importing any Qt modules
os.environ['QT_API'] = 'PyQt6'

import argparse
import shutil
import numpy as np

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QLineEdit, QPushButton, QLabel, QFileDialog,
                            QDialog, QDialogButtonBox, QScrollArea, QHBoxLayout,
                            QMessageBox, QComboBox)
from PyQt6.QtGui import QPixmap, QWheelEvent, QPainter, QPalette, QPen, QColor, QImage
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer
from picamera2 import Picamera2, Preview
# Comment out Qt preview due to PyQt5/PyQt6 compatibility issues
# from picamera2.previews.qt import QGlPicamera2, QPicamera2

# You can override these here, if you wish, or on the command line.
USER = ""
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "awb-images")
TMP_DIR = "/dev/shm"
CAMERA = 1

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selection_start = None
        self.selection_end = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selection_start and self.selection_end:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine))
            rect = QRect(self.selection_start, self.selection_end).normalized()
            painter.drawRect(rect)

class ImageDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Rectangle")
        self.setModal(True)
        self.setGeometry(50, 50, 1200, 900)  # Increased dialog size
        
        # Add property to store the selected rectangle
        self.selected_rect = None
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        self.setLayout(layout)
        
        # Create scroll area for panning
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)  # Remove frame
        layout.addWidget(self.scroll_area)
        
        # Create label for displaying image
        self.image_label = ImageLabel()
        self.scroll_area.setWidget(self.image_label)

        # Add instructions
        instructions = QLabel("Click and drag to pan. Mouse wheel to zoom. Ctrl+Click and drag to set rectangle.")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions)

        # Add Done button in a centered layout
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(10, 10, 10, 10)  # Add some margin around the button
        button_layout.addStretch(1)
        button_box = QDialogButtonBox()
        done_button = button_box.addButton("Done", QDialogButtonBox.ButtonRole.AcceptRole)
        done_button.clicked.connect(self.accept)
        button_layout.addWidget(button_box)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)

        # Initialize zoom and pan variables
        self.zoom_factor = 1.0
        self.min_zoom_factor = 1.0
        self.pan_start = QPoint()
        self.panning = False
        self.original_pixmap = None

        # Initialize selection rectangle variables
        self.is_selecting = False
        self.ctrl_pressed = False

        # Enable mouse tracking for panning
        self.image_label.setMouseTracking(True)
        self.image_label.mousePressEvent = self.mousePressEvent
        self.image_label.mouseMoveEvent = self.mouseMoveEvent
        self.image_label.mouseReleaseEvent = self.mouseReleaseEvent
        self.image_label.wheelEvent = self.wheelEvent

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self.ctrl_pressed = True
            self.image_label.setCursor(Qt.CursorShape.CrossCursor)
            # Clear previous selection when Ctrl is pressed
            self.image_label.selection_start = None
            self.image_label.selection_end = None
            self.image_label.update()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self.ctrl_pressed = False
            self.image_label.setCursor(Qt.CursorShape.ArrowCursor)
            # Don't clear the selection when Ctrl is released
        super().keyReleaseEvent(event)

    def set_image(self, pixmap):
        self.original_pixmap = pixmap
        # We'll calculate the zoom factor in showEvent

    def showEvent(self, event):
        super().showEvent(event)
        if self.original_pixmap is not None:
            self.update_min_zoom_factor()
            self.zoom_factor = self.min_zoom_factor
            self.update_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_pixmap is not None:
            self.update_min_zoom_factor()
            # If current zoom is less than min, update to min
            if self.zoom_factor < self.min_zoom_factor:
                self.zoom_factor = self.min_zoom_factor
                self.update_image()

    def update_min_zoom_factor(self):
        # Calculate initial zoom factor to fill the window
        viewport_size = self.scroll_area.viewport().size()
        
        # Calculate zoom factors for width and height
        width_ratio = viewport_size.width() / self.original_pixmap.width()
        height_ratio = viewport_size.height() / self.original_pixmap.height()
        
        # Use the larger ratio to fill the window
        self.min_zoom_factor = max(width_ratio, height_ratio)

    def update_image(self):
        # Scale the image based on current zoom factor
        scaled_pixmap = self.original_pixmap.scaled(
            self.original_pixmap.size() * self.zoom_factor,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.adjustSize()

    def wheelEvent(self, event: QWheelEvent):
        # Get current scroll positions
        old_h_scroll = self.scroll_area.horizontalScrollBar().value()
        old_v_scroll = self.scroll_area.verticalScrollBar().value()
        
        # Get mouse position relative to the viewport
        mouse_pos = event.position().toPoint()
        
        # Calculate position relative to the image
        image_pos = QPoint(
            mouse_pos.x() + old_h_scroll,
            mouse_pos.y() + old_v_scroll
        )

        # Calculate the position as a ratio of the image size
        image_size = self.image_label.size()
        pos_ratio_x = image_pos.x() / image_size.width()
        pos_ratio_y = image_pos.y() / image_size.height()
        
        # Zoom in/out with mouse wheel
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_factor *= 1.1  # Zoom in
        else:
            self.zoom_factor *= 0.9  # Zoom out
        
        # Limit zoom range
        self.zoom_factor = max(self.min_zoom_factor, min(5.0, self.zoom_factor))
        self.update_image()
        
        # Calculate new image size
        new_image_size = self.image_label.size()
        
        # Calculate the new scroll positions to keep the same pixel under the mouse
        new_h_scroll = int(pos_ratio_x * new_image_size.width() - mouse_pos.x())
        new_v_scroll = int(pos_ratio_y * new_image_size.height() - mouse_pos.y())
        
        # Ensure scroll positions are within valid range
        h_scroll_bar = self.scroll_area.horizontalScrollBar()
        v_scroll_bar = self.scroll_area.verticalScrollBar()
        
        new_h_scroll = max(0, min(new_h_scroll, h_scroll_bar.maximum()))
        new_v_scroll = max(0, min(new_v_scroll, v_scroll_bar.maximum()))
        
        # Set new scroll positions
        h_scroll_bar.setValue(new_h_scroll)
        v_scroll_bar.setValue(new_v_scroll)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.ctrl_pressed:
                self.is_selecting = True
                self.image_label.selection_start = event.position().toPoint()
                self.image_label.selection_end = event.position().toPoint()
            else:
                self.pan_start = event.position().toPoint()
                self.panning = True
                self.image_label.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.ctrl_pressed and self.is_selecting:
            self.image_label.selection_end = event.position().toPoint()
            self.image_label.update()
        elif self.panning:
            delta = event.position().toPoint() - self.pan_start
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x()
            )
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y()
            )
            self.pan_start = event.position().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.ctrl_pressed:
                self.is_selecting = False
                if self.image_label.selection_start and self.image_label.selection_end:
                    # Convert selection coordinates to image coordinates
                    # The selection coordinates are already in the viewport's coordinate space,
                    # so we just need to divide by zoom_factor to get back to original image coordinates
                    start_x = int(self.image_label.selection_start.x() / self.zoom_factor)
                    start_y = int(self.image_label.selection_start.y() / self.zoom_factor)
                    end_x = int(self.image_label.selection_end.x() / self.zoom_factor)
                    end_y = int(self.image_label.selection_end.y() / self.zoom_factor)
                    
                    # Create rectangle in original image coordinates
                    rect = QRect(
                        min(start_x, end_x),
                        min(start_y, end_y),
                        abs(end_x - start_x),
                        abs(end_y - start_y)
                    )
                    
                    # Store the rectangle in original image coordinates
                    self.selected_rect = {
                        'x': rect.x(),
                        'y': rect.y(),
                        'width': rect.width(),
                        'height': rect.height()
                    }
                    print(f"Selected rectangle (pixels): {self.selected_rect}")
            else:
                self.panning = False
                self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

class CameraPreviewLabel(QLabel):
    """Custom camera preview class as replacement for picamera2 Qt widgets"""
    
    def __init__(self, picam2, parent=None):
        super().__init__(parent)
        self.picam2 = picam2
        self.setMinimumSize(640, 480)
        self.setStyleSheet("border: 1px solid gray;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Camera preview loading...")
        
        # Timer for preview updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_preview)
        self.update_timer.start(33)  # ~30 FPS
        
        # Dummy signal for compatibility
        self.done_signal = self
        
    def connect(self, slot):
        """Dummy method for compatibility with picamera2 Qt widgets"""
        self.capture_done_slot = slot
        
    def signal_done(self, job):
        """Dummy method for compatibility with picamera2 Qt widgets"""
        if hasattr(self, 'capture_done_slot'):
            self.capture_done_slot(job)
    
    def update_preview(self):
        """Update the preview image"""
        try:
            # Get the current frame from the camera
            array = self.picam2.capture_array()
            
            # Check array format and convert accordingly
            if array.ndim == 3:
                h, w, ch = array.shape
                if ch == 3:
                    # RGB format
                    bytes_per_line = ch * w
                    qt_image = QImage(array.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                elif ch == 4:
                    # RGBA format
                    bytes_per_line = ch * w
                    qt_image = QImage(array.data, w, h, bytes_per_line, QImage.Format.Format_RGBA8888)
                else:
                    # Unknown format - use fallback
                    self.setText(f"Unknown color format: {ch} channels")
                    return
            elif array.ndim == 2:
                # Grayscale image
                h, w = array.shape
                bytes_per_line = w
                qt_image = QImage(array.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
            else:
                # YUV420 or other format - use alternative approach
                try:
                    # Try RGB conversion via picamera2
                    rgb_array = self.picam2.capture_array("main")
                    if rgb_array.ndim == 3 and rgb_array.shape[2] >= 3:
                        h, w = rgb_array.shape[:2]
                        ch = min(rgb_array.shape[2], 3)  # Use maximum 3 channels
                        # Crop to RGB if more channels available
                        if rgb_array.shape[2] > 3:
                            rgb_array = rgb_array[:, :, :3]
                        bytes_per_line = ch * w
                        qt_image = QImage(rgb_array.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                    else:
                        self.setText("Camera format not supported")
                        return
                except:
                    self.setText("Error during RGB capture")
                    return
            
            # Scale the image to widget size
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
            
        except Exception as e:
            # On errors, show error message
            self.setText(f"Preview error: {str(e)}")
            # Debug-Info
            try:
                array = self.picam2.capture_array()
                print(f"Debug: Array shape: {array.shape}, dtype: {array.dtype}")
            except:
                print("Debug: No array available")

class AwbOMatic(QMainWindow):
    def __init__(self, user=USER, output_dir=OUTPUT_DIR, tmp_dir=TMP_DIR, camera=CAMERA, ssh_mode=False):
        super().__init__()

        self.tmp_jpg = os.path.join(tmp_dir, "tmp.jpg")
        self.tmp_dng = os.path.join(tmp_dir, "tmp.dng")
        self.output_dir = output_dir
        self.user = user

        # Detect available cameras
        self.available_cameras = self.detect_cameras()
        
        # Configure initial camera
        if camera in self.available_cameras:
            self.current_camera = camera
        else:
            self.current_camera = self.available_cameras[0] if self.available_cameras else 0
            
        self.configure_camera(self.current_camera)

        self.setWindowTitle("AWB-O-Matic")
        self.setGeometry(100, 100, 1000, 800)  # Increased main window size

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add EV control buttons
        self.ev_value = 0
        ev_button_layout = QHBoxLayout()

        self.capture_button = QPushButton("Capture")
        self.update_capture_button_style()  # Set initial color
        self.capture_button.clicked.connect(self.capture)
        ev_button_layout.addWidget(self.capture_button)

        # Camera selection at second position without label
        self.camera_combo = QComboBox()
        for cam_id in self.available_cameras:
            self.camera_combo.addItem(f"Cam{cam_id}", cam_id)
        
        # Select current camera
        current_index = self.camera_combo.findData(self.current_camera)
        if current_index >= 0:
            self.camera_combo.setCurrentIndex(current_index)
            
        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)
        ev_button_layout.addWidget(self.camera_combo)

        ev_down_button = QPushButton("EV-")
        ev_down_button.clicked.connect(self.ev_down)
        ev_button_layout.addWidget(ev_down_button)

        ev_up_button = QPushButton("EV+")
        ev_up_button.clicked.connect(self.ev_up)
        ev_button_layout.addWidget(ev_up_button)

        self.ev_value_label = QLabel(f"EV: {self.ev_value}")
        ev_button_layout.addWidget(self.ev_value_label)

        layout.addLayout(ev_button_layout)

        bg_colour = self.palette().color(QPalette.ColorRole.Window).getRgb()[:3]
        # if ssh_mode:
        #     self.qpicamera2 = QPicamera2(self.picam2, bg_colour=bg_colour)
        # else:
        #     self.qpicamera2 = QGlPicamera2(self.picam2, bg_colour=bg_colour)

        # self.qpicamera2.done_signal.connect(self.capture_done)

        # self.qpicamera2.setFixedSize(1024, 768)
        # layout.addWidget(self.qpicamera2)
        # Use custom preview class instead of picamera2 Qt widgets
        self.camera_preview = CameraPreviewLabel(self.picam2, self)
        self.camera_preview.connect(self.capture_done)
        self.camera_preview.setFixedSize(1024, 768)
        layout.addWidget(self.camera_preview)

        # Display USER value
        user_label = QLabel(f"User: {user}")
        layout.addWidget(user_label)

        # Display sensor information
        sensor_label = QLabel(f"Sensor: {self.sensor}")
        layout.addWidget(sensor_label)

        # Add scene ID input with label
        scene_id_layout = QHBoxLayout()
        scene_id_label = QLabel("Scene Id:")
        scene_id_layout.addWidget(scene_id_label)
        self.scene_id_input = QLineEdit()
        self.scene_id_input.setPlaceholderText("Scene Id is required")
        scene_id_layout.addWidget(self.scene_id_input)
        layout.addLayout(scene_id_layout)

        # Create view button
        button_layout = QHBoxLayout()
        add_rectangle_button = QPushButton("Add Rectangle")
        add_rectangle_button.clicked.connect(self.add_rectangle)
        button_layout.addWidget(add_rectangle_button)

        clear_rectangle_button = QPushButton("Clear Rectangle")
        clear_rectangle_button.clicked.connect(self.clear_rectangle)
        button_layout.addWidget(clear_rectangle_button)

        # Add label to show current rectangle value
        self.rect_value_label = QLabel("No rectangle selected")
        self.rect_value_label.setWordWrap(True)
        button_layout.addWidget(self.rect_value_label)

        layout.addLayout(button_layout)

        # Display output directory at the bottom
        output_dir_label = QLabel(f"Output directory: {output_dir}")
        layout.addWidget(output_dir_label)

        # Add Rename Image button with horizontal layout for centering
        rename_layout = QHBoxLayout()
        rename_layout.addStretch(1)
        rename_button = QPushButton("Rename Image")
        rename_button.setMinimumWidth(200)
        rename_button.setStyleSheet("""
            QPushButton {
                padding: 8px;
                font-weight: bold;
                background-color: #4CAF50;
                color: white;
                border: 2px solid #45a049;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3e8e41;
            }
        """)
        rename_button.clicked.connect(self.rename_image)
        rename_layout.addWidget(rename_button)
        rename_layout.addStretch(1)
        layout.addLayout(rename_layout)

        # Store rectangle information
        self.selected_rect = None

        self.picam2.start()

    def detect_cameras(self):
        """Detect available cameras"""
        from picamera2 import Picamera2
        available_cameras = []
        
        try:
            # Test cameras 0 and 1
            for cam_id in [0, 1]:
                try:
                    temp_cam = Picamera2(cam_id)
                    # Check if camera is available
                    camera_info = temp_cam.camera_properties
                    if camera_info:
                        available_cameras.append(cam_id)
                        print(f"Camera {cam_id} detected: {camera_info.get('Model', 'Unknown')}")
                    temp_cam.close()
                except Exception as e:
                    print(f"Camera {cam_id} not available: {e}")
                    continue
        except Exception as e:
            print(f"Error detecting cameras: {e}")
            # Fallback to camera 0
            available_cameras = [0]
            
        if not available_cameras:
            available_cameras = [0]  # Fallback
            
        return available_cameras

    def on_camera_changed(self, index):
        """Callback when camera is changed"""
        if index < 0:
            return
            
        new_camera = self.camera_combo.itemData(index)
        if new_camera != self.current_camera:
            try:
                # Stop current camera
                if hasattr(self, 'picam2'):
                    self.picam2.stop()
                    self.picam2.close()
                
                # Stop preview timer
                if hasattr(self, 'camera_preview'):
                    self.camera_preview.update_timer.stop()
                
                # Configure new camera
                self.current_camera = new_camera
                self.configure_camera(self.current_camera)
                
                # Update preview
                self.camera_preview = CameraPreviewLabel(self.picam2, self)
                self.camera_preview.connect(self.capture_done)
                self.camera_preview.setFixedSize(1024, 768)
                
                # Find the old preview widget and replace it
                layout = self.centralWidget().layout()
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() and isinstance(item.widget(), CameraPreviewLabel):
                        old_widget = item.widget()
                        layout.removeWidget(old_widget)
                        old_widget.deleteLater()
                        layout.insertWidget(i, self.camera_preview)
                        break
                
                # Start new camera
                self.picam2.start()
                
                # Update capture button style based on new camera
                self.update_capture_button_style()
                
                print(f"Switched to camera {new_camera}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to switch camera: {str(e)}")
                # Reset dropdown
                old_index = self.camera_combo.findData(self.current_camera)
                if old_index >= 0:
                    self.camera_combo.setCurrentIndex(old_index)

    def update_capture_button_style(self):
        """Updates the capture button style based on the current camera"""
        if self.current_camera == 0:
            # Cam0 = blue
            color = "#2196F3"  # Blue
            hover_color = "#1976D2"
            pressed_color = "#1565C0"
            border_color = "#1976D2"
        else:
            # Cam1 = green
            color = "#4CAF50"  # Green
            hover_color = "#388E3C"
            pressed_color = "#2E7D32"
            border_color = "#388E3C"
        
        style = f"""
            QPushButton {{
                padding: 8px;
                font-weight: bold;
                background-color: {color};
                color: white;
                border: 2px solid {border_color};
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
            }}
            QPushButton:disabled {{
                background-color: #BDBDBD;
                border-color: #9E9E9E;
            }}
        """
        self.capture_button.setStyleSheet(style)

    def configure_camera(self, camera):
        self.picam2 = Picamera2(camera)
        self.sensor = self.picam2.camera_properties['Model']
        if 'mono' in self.sensor.lower() or 'noir' in self.sensor.lower():
            raise ValueError("Mono/Noir cameras are not supported - please use a colour camera")
        self.capture_config = self.picam2.create_still_configuration()
        full_res = self.picam2.sensor_resolution
        half_res = (full_res[0] // 2, full_res[1] // 2)
        preview_res = half_res
        while preview_res[0] > 1280:
            preview_res = (preview_res[0] // 2, preview_res[1] // 2)
        self.preview_res = preview_res
        print(f"Preview resolution: {preview_res}")
        preview_config = self.picam2.create_preview_configuration(
            {'format': 'YUV420', 'size': preview_res},
            raw={'format': 'SBGGR12', 'size': half_res}, # force unpacked, full FOV
            controls={'FrameRate': 30}
        )
        self.picam2.configure(preview_config)
        if 'AfMode' in self.picam2.camera_controls:
            self.picam2.set_controls({"AfMode": 2})  # Continuous AF, where available
 
    def ev_up(self):
        self.ev_value += 0.125
        self.picam2.set_controls({"ExposureValue": self.ev_value})
        self.ev_value_label.setText(f"EV: {self.ev_value}")

    def ev_down(self):
        self.ev_value -= 0.125
        self.picam2.set_controls({"ExposureValue": self.ev_value})
        self.ev_value_label.setText(f"EV: {self.ev_value}")

    def capture(self):
        self.capture_button.setEnabled(False)
        print("Doing capture")
        self.picam2.switch_mode_and_capture_request(
            self.capture_config, wait=False, signal_function=self.camera_preview.signal_done)

    def capture_done(self, job):
        self.capture_button.setEnabled(True)
        request = job.get_result()
        request.save('main', self.tmp_jpg)
        request.save_dng(self.tmp_dng)
        print("Capture done", request)
        request.release()

    def is_valid_filename(self, text):
        # List of characters not allowed in filenames
        invalid_chars = '<>:"/\\|?*,\''
        return not any(char in invalid_chars for char in text)

    def rename_image(self):
        scene_id = self.scene_id_input.text().strip()
        if not scene_id:
            QMessageBox.warning(self, "Warning", "A scene ID is required before renaming the image")
            return
        if not self.is_valid_filename(scene_id):
            QMessageBox.warning(self, "Warning", 
                "Scene ID contains invalid characters. Please avoid: < > : \" / \\ | ? * , '")
            return

        # Check if temporary files exist
        if not os.path.exists(self.tmp_jpg) or not os.path.exists(self.tmp_dng):
            QMessageBox.warning(self, "Warning", 
                "No captured images found. Please capture an image first.")
            return

        if self.selected_rect:
            x0 = self.selected_rect['x']
            y0 = self.selected_rect['y']
            x1 = x0 + self.selected_rect['width']
            y1 = y0 + self.selected_rect['height']
            basename = f"{self.user},{self.sensor},{scene_id},{x0},{y0},{x1},{y1}"
        else:
            basename = f"{self.user},{self.sensor},{scene_id}"
        jpg_filename = os.path.join(self.output_dir, basename + ".jpg")
        dng_filename = os.path.join(self.output_dir, basename + ".dng")

        # Check if files already exist
        if os.path.exists(jpg_filename) or os.path.exists(dng_filename):
            reply = QMessageBox.warning(self, 'Warning',
                f"Files already exist:\n\n"
                f"{basename}.jpg\n"
                f"{basename}.dng\n\n"
                "Do you want to overwrite them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.No:
                return
        else:
            # Show confirmation dialog
            reply = QMessageBox.question(self, 'Confirm Rename',
                f"Rename files to:\n\n"
                f"{basename}.jpg\n"
                f"{basename}.dng\n\n"
                "Do you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.No:
                return

        try:
            # Move the files
            shutil.move(self.tmp_jpg, jpg_filename)
            shutil.move(self.tmp_dng, dng_filename)
            QMessageBox.information(self, "Success", "Files renamed successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to rename files: {str(e)}")

    def clear_rectangle(self):
        self.selected_rect = None
        self.rect_value_label.setText("No rectangle selected")

    def add_rectangle(self):
        try:
            pixmap = QPixmap(self.tmp_jpg)
            if not pixmap.isNull():
                dialog = ImageDialog(self)
                dialog.set_image(pixmap)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    if dialog.selected_rect:
                        self.selected_rect = dialog.selected_rect
                        rect_text = (
                            f"x: {self.selected_rect['x']}, y: {self.selected_rect['y']} "
                            f"width: {self.selected_rect['width']}, height: {self.selected_rect['height']}"
                        )
                        self.rect_value_label.setText(rect_text)

                        # Also check the saturation of the rectangle
                        size = pixmap.size()
                        w = size.width()
                        h = size.height()
                        qimg = pixmap.toImage()
                        qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
                        bytes = qimg.bits()
                        bytes.setsize(w * h * 4)
                        array = np.frombuffer(bytes, dtype=np.uint8).reshape((h, w, 4))
                        x0 = self.selected_rect['x']
                        y0 = self.selected_rect['y']
                        x1 = x0 + self.selected_rect['width']
                        y1 = y0 + self.selected_rect['height']
                        r_avg = array[y0:y1, x0:x1, 0].mean()
                        g_avg = array[y0:y1, x0:x1, 1].mean()
                        b_avg = array[y0:y1, x0:x1, 2].mean()
                        print("RGB means:", r_avg, g_avg, b_avg)
                        if r_avg > 220 or g_avg > 220 or b_avg > 220:
                            QMessageBox.warning(self, "Warning",
                                                "Rectangle looks bright - consider re-capturing with lower EV")

                    else:
                        self.clear_rectangle()
            else:
                QMessageBox.warning(self, "Warning", "Could not load image - please do capture first")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

if __name__ == '__main__':
    # Create QApplication first - required before any Qt widgets
    app = QApplication(sys.argv)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='AWB-O-Matic Tool')
    parser.add_argument('-u', '--user', help='Set the user name for saved images')
    parser.add_argument('-o', '--output', help='Override the output directory')
    parser.add_argument('-t', '--tmp', help='Override the temporary directory')
    ssh_group = parser.add_mutually_exclusive_group()
    ssh_group.add_argument('-s', '--ssh', action='store_true', help='Enable SSH mode')
    ssh_group.add_argument('--no-ssh', action='store_true', help='Disable SSH mode')
    args = parser.parse_args()

    # Override USER if command line argument is provided
    if args.user:
        USER = args.user

    # Override OUTPUT_DIR if command line argument is provided
    if args.output:
        OUTPUT_DIR = args.output

    # Override TMP_DIR if command line argument is provided
    if args.tmp:
        TMP_DIR = args.tmp

    # Create directories if they don't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    # Check if USER is set
    if not USER:
        parser.error("User name must be set. Use -u/--user to specify a user name.")

    # Check for invalid characters in USER
    invalid_chars = '<>:"/\\|?*,\''
    if any(char in invalid_chars for char in USER):
        parser.error(f"User name contains invalid characters. Please avoid: {invalid_chars}")

    # Set SSH mode based on arguments or environment
    ssh_mode = None
    if args.ssh:
        ssh_mode = True
    elif args.no_ssh:
        ssh_mode = False
    else:
        # Try to deduce SSH status from DISPLAY environment variable
        display = os.environ.get('DISPLAY', '')
        if display.startswith('localhost:') or display.startswith('127.0.0.1:'):
            ssh_mode = True
        elif display:
            ssh_mode = False

    print(f"User: {USER}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Temporary directory: {TMP_DIR}")
    print(f"SSH mode: {ssh_mode}")

    window = AwbOMatic(user=USER, output_dir=OUTPUT_DIR, tmp_dir=TMP_DIR, ssh_mode=ssh_mode)
    window.show()
    sys.exit(app.exec())