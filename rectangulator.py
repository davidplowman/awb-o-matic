#! /usr/bin/env python3

import sys
import os
import argparse
import shutil
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QLineEdit, QPushButton, QLabel, QFileDialog,
                            QDialog, QDialogButtonBox, QScrollArea, QHBoxLayout,
                            QMessageBox, QListWidget, QSplitter, QSizePolicy, QListWidgetItem)
from PyQt5.QtGui import QPixmap, QWheelEvent, QPainter, QPalette, QPen, QColor, QImage
from PyQt5.QtCore import Qt, QPoint, QRect

# You can override these here, if you wish, or on the command line.
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "awb-images")
INPUT_DIR = os.path.join(os.path.expanduser("~"), "awb-captures")

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selection_start = None
        self.selection_end = None
        self.setAlignment(Qt.AlignCenter)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selection_start and self.selection_end:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.DashLine))
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
        self.MIN_SIZE = 10  # Minimum size for selection in pixels

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        self.setLayout(layout)

        # Create scroll area for panning
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)  # Remove frame
        layout.addWidget(self.scroll_area)

        # Create label for displaying image
        self.image_label = ImageLabel()
        self.scroll_area.setWidget(self.image_label)

        # Add instructions
        instructions = QLabel("Click and drag to pan. Mouse wheel to zoom. Ctrl+Click and drag to set grey rectangle. Click the Accept button to finish.")
        instructions.setAlignment(Qt.AlignCenter)
        layout.addWidget(instructions)

        # Add Done button in a centered layout
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(10, 10, 10, 10)  # Add some margin around the button
        button_layout.addStretch(1)
        button_box = QDialogButtonBox()
        self.accept_button = button_box.addButton("Accept", QDialogButtonBox.AcceptRole)
        self.accept_button.clicked.connect(self.accept)
        self.accept_button.setEnabled(False)  # Initially disabled
        cancel_button = button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        cancel_button.clicked.connect(self.on_cancel)
        button_layout.addWidget(button_box)
        button_layout.addStretch(1)
        layout.addLayout(button_layout)

        # Initialize zoom and pan variables
        self.zoom_factor = 1.0
        self.min_zoom_factor = 1.0
        self.pan_start = QPoint()
        self.panning = False
        self.original_pixmap = None
        self.backup_pixmap = None

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
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = True
            self.image_label.setCursor(Qt.CrossCursor)
            # Clear previous selection when Ctrl is pressed
            self.image_label.selection_start = None
            self.image_label.selection_end = None
            self.image_label.update()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = False
            self.image_label.setCursor(Qt.ArrowCursor)
            # Don't clear the selection when Ctrl is released
        super().keyReleaseEvent(event)

    def set_image(self, pixmap):
        self.original_pixmap = pixmap
        # Create a backup copy of the original pixmap
        self.backup_pixmap = QPixmap(pixmap)
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
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.adjustSize()

    def wheelEvent(self, event: QWheelEvent):
        # Clear rectangle when zooming
        self.image_label.selection_start = None
        self.image_label.selection_end = None
        self.image_label.update()

        # Get current scroll positions
        old_h_scroll = self.scroll_area.horizontalScrollBar().value()
        old_v_scroll = self.scroll_area.verticalScrollBar().value()

        # Get mouse position relative to the viewport
        mouse_pos = event.pos()

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
        if event.button() == Qt.LeftButton:
            if self.ctrl_pressed:
                self.is_selecting = True
                self.image_label.selection_start = event.pos()
                self.image_label.selection_end = event.pos()
            else:
                # Clear rectangle when starting to pan
                self.image_label.selection_start = None
                self.image_label.selection_end = None
                self.image_label.update()
                self.pan_start = event.pos()
                self.panning = True
                self.image_label.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.ctrl_pressed and self.is_selecting:
            self.image_label.selection_end = event.pos()
            self.image_label.update()
        elif self.panning:
            delta = event.pos() - self.pan_start
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x()
            )
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y()
            )
            self.pan_start = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
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

                    # Only accept selection if it's large enough
                    if rect.width() >= self.MIN_SIZE and rect.height() >= self.MIN_SIZE:
                        # Store the rectangle in original image coordinates
                        self.selected_rect = {
                            'x': rect.x(),
                            'y': rect.y(),
                            'width': rect.width(),
                            'height': rect.height()
                        }
                        print(f"Selected rectangle:", self.selected_rect)
                        self.accept_button.setEnabled(True)  # Enable Accept button when valid selection is made

                        # Convert backup pixmap to numpy array
                        image = self.backup_pixmap.toImage()
                        width = image.width()
                        height = image.height()
                        ptr = image.bits()
                        ptr.setsize(height * width * 4)  # 4 bytes per pixel (RGBA)
                        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
                        # Convert RGBA to RGB
                        rgb_arr = arr[:, :, :3]

                         # Square the pixel values as a kind of fake gamma correction
                        rgb_float = rgb_arr.astype(np.float32) / 255
                        rgb_float *= rgb_float

                        # Use a middle-of-the-road generic colour correction matrix.
                        ccm = np.transpose(np.array([[1.8, -0.8, 0], [-0.4, 1.8, -0.4], [0, -0.8, 1.8]]))
                        inv_ccm = np.linalg.inv(ccm)
                        rgb_float = rgb_float @ inv_ccm
                        rgb_float = np.clip(rgb_float, 0, 1)

                       # Calculate average RGB values for the selected rectangle
                        x, y = self.selected_rect['x'], self.selected_rect['y']
                        w, h = self.selected_rect['width'], self.selected_rect['height']
                        rect_pixels = rgb_float[y:y+h, x:x+w]
                        avg_rgb = np.mean(rect_pixels, axis=(0, 1)) + 0.001 # Add 0.001 to avoid division by zero
                        print(f"Average RGB values: R={avg_rgb[2]:.3f}, G={avg_rgb[1]:.3f}, B={avg_rgb[0]:.3f}")

                        # Check for saturation
                        if np.any(avg_rgb > 0.85):
                            QMessageBox.warning(self, "Warning", "Rectangle too saturated - choose another")
                            self.image_label.selection_start = None
                            self.image_label.selection_end = None
                            self.image_label.update()
                            self.accept_button.setEnabled(False)
                            return

                        # Calculate gains relative to green channel
                        gain_r = avg_rgb[1] / avg_rgb[2]  # Green/Red
                        gain_b = avg_rgb[1] / avg_rgb[0]  # Green/Blue
                        gain_g = 1.0
                        min_gain = min(gain_r, gain_b, gain_g)
                        gain_r = gain_r / min_gain
                        gain_b = gain_b / min_gain
                        gain_g = gain_g / min_gain
                        print(f"Gain values: R={gain_r:.3f}, B={gain_b:.3f}, G={gain_g:.3f}")

                        # Apply gains to the image
                        rgb_float[:, :, 2] = np.clip(rgb_float[:, :, 2] * gain_r, 0, 1)  # Red channel
                        rgb_float[:, :, 0] = np.clip(rgb_float[:, :, 0] * gain_b, 0, 1)  # Blue channel
                        rgb_float[:, :, 1] = np.clip(rgb_float[:, :, 1] * gain_g, 0, 1)  # Green channel

                        rgb_float = rgb_float @ ccm
                        rgb_float = np.clip(rgb_float, 0, 1)
                        # Square root the pixel values to undo the gamma correction
                        rgb_float = np.sqrt(rgb_float)

                        # Convert back to uint8 and scale to 0-255
                        rgb_arr = (rgb_float * 255).astype(np.uint8)

                        # Convert back to QPixmap
                        height, width = rgb_arr.shape[:2]
                        bytes_per_line = 3 * width
                        # Convert numpy array to bytes and swap red and blue channels
                        rgb_arr = rgb_arr.astype(np.uint8)
                        # Swap red and blue channels to match RGB888 format
                        rgb_arr = rgb_arr[:, :, ::-1]  # Reverse the channel order
                        q_img = QImage(rgb_arr.tobytes(), width, height, bytes_per_line, QImage.Format_RGB888)
                        self.original_pixmap = QPixmap.fromImage(q_img)
                        self.update_image()
                    else:
                        # Clear the selection if it's too small
                        self.image_label.selection_start = None
                        self.image_label.selection_end = None
                        self.image_label.update()
                        self.accept_button.setEnabled(False)  # Disable Accept button when selection is cleared
            else:
                self.panning = False
                self.image_label.setCursor(Qt.ArrowCursor)

    def on_cancel(self):
        """Handle cancel button click by clearing selection and closing dialog"""
        self.image_label.selection_start = None
        self.image_label.selection_end = None
        self.image_label.update()
        self.selected_rect = None
        self.accept_button.setEnabled(False)  # Disable Accept button when canceling
        self.reject()

class Rectangulator(QMainWindow):
    def __init__(self, input_dir=INPUT_DIR, output_dir=OUTPUT_DIR):
        super().__init__()
        self.setWindowTitle("AWB Rectangulator")
        self.setGeometry(100, 100, 1200, 900)

        # Store directories
        self.input_dir = input_dir
        self.output_dir = output_dir

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        # Track processed files
        self.processed_files = set()

        # Create main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)  # Changed to QVBoxLayout

        # Add directory labels at the top
        dir_layout = QHBoxLayout()
        dir_layout.setContentsMargins(5, 2, 5, 2)  # Minimize vertical margins
        input_label = QLabel(f"Input: {self.input_dir}")
        output_label = QLabel(f"Output: {self.output_dir}")
        input_label.setStyleSheet("color: #666666; font-weight: bold;")
        output_label.setStyleSheet("color: #666666; font-weight: bold;")
        # Set size policies to prevent vertical expansion
        input_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        output_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        dir_layout.addWidget(input_label)
        dir_layout.addWidget(output_label)
        dir_layout.addStretch()
        self.main_layout.addLayout(dir_layout)

        # Add instruction label
        instruction_label = QLabel("Double-click a file to select a grey rectangle and copy to output folder")
        instruction_label.setStyleSheet("color: #666666; font-style: italic;")
        instruction_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        instruction_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.main_layout.addWidget(instruction_label)

        # Create splitter for resizable panes
        self.splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.splitter)

        # Create file list widget
        self.file_list = QListWidget()
        self.file_list.setMinimumWidth(200)
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        # Set a brighter background color
        self.file_list.setStyleSheet("background-color: #3D3D3D; color: #FFFFFF;")
        self.splitter.addWidget(self.file_list)

        # Create main content area
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.splitter.addWidget(self.content_area)

        # Load files
        self.load_files()

    def load_files(self):
        """Load JPG files from input directory into the list widget"""
        self.file_list.clear()
        try:
            files = [f for f in os.listdir(self.input_dir) if f.lower().endswith('.jpg')]
            files.sort()
            for file in files:
                # Remove any existing checkmark from the filename
                display_name = file.replace("✓ ", "")
                item = QListWidgetItem(display_name)
                # Add checkmark if file has been processed
                if file in self.processed_files:
                    item.setText(f"✓ {display_name}")
                self.file_list.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load files: {str(e)}")

    def on_file_double_clicked(self, item):
        """Handle double-click on a file in the list"""
        filename = item.text()
        self.process_file(filename)

    def process_file(self, filename):
        """Process the selected file by loading and displaying it in ImageDialog"""
        try:
            # Remove any checkmark from the filename
            clean_filename = filename.replace("✓ ", "")

            # Construct full path to the image
            image_path = os.path.join(self.input_dir, clean_filename)

            # Load the image
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", f"Failed to load image: {clean_filename}")
                return

            # Create and show the image dialog
            dialog = ImageDialog(self)
            dialog.set_image(pixmap)
            result = dialog.exec_()

            # After dialog is closed, check if it was accepted
            if result == QDialog.Accepted and dialog.selected_rect:
                print(f"Selected rectangle for {clean_filename}: {dialog.selected_rect}")
                # Add file to processed set
                self.processed_files.add(clean_filename)

                x0, y0, w, h = dialog.selected_rect['x'], dialog.selected_rect['y'], dialog.selected_rect['width'], dialog.selected_rect['height']
                x1, y1 = x0 + w, y0 + h

                new_filename = clean_filename.replace(".jpg", f",{x0},{y0},{x1},{y1}.jpg")
                new_image_path = os.path.join(self.output_dir, new_filename)
                shutil.copy(image_path, new_image_path)
                print(f"Copied {image_path} to {new_image_path}")

                dng_path = image_path.replace(".jpg", ".dng")
                new_dng_path = new_image_path.replace(".jpg", ".dng")
                shutil.copy(dng_path, new_dng_path)
                print(f"Copied {dng_path} to {new_dng_path}")

                self.load_files()
            else:
                print(f"No rectangle selected for {clean_filename}")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error processing file {clean_filename}: {str(e)}")

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='AWB-O-Matic Tool')
    parser.add_argument('--input-dir', type=str, default=INPUT_DIR,
                      help=f'Input directory containing images (default: {INPUT_DIR})')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR,
                      help=f'Output directory for processed images (default: {OUTPUT_DIR})')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = Rectangulator(input_dir=args.input_dir, output_dir=args.output_dir)
    window.show()
    sys.exit(app.exec_())
