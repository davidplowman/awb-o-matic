# AWB-O-Matic

These are a small suite of tools for capturing images for Auto White Balance (AWB) calibration.

Firstly we have the AWB-O-Matic tool itself (awb-o-matic.py) which captures images and immediately lets the user annotate them with the coordinates of a rectangle where the image is grey.

But sometimes this is not a convenient workflow so we have two further tools which break up the process into a couple of separate stages.

- The Snapper tool is for capturing images, but it does nothing further with them at the time. So it's great just for wandering around snapping away.
- The Rectangulator tool allows users to analyse the Snapper's images, and annotate them with a rectangle where the image is grey. The Rectangulator can be run later, optionally on a computer that is not a Pi.

## Installation

The AWB-O-Matic and Snapper tools only run on the Raspberry Pi where all the required dependencies should already be available. It should be sufficient to clone this repository:
```bash
git clone https://github.com/davidplowman/awb-o-matic.git
cd awb-o-matic
```

The Rectangulator will run on other devices. Its requirements include PyQt5, numpy and a handful of other standard Python packages.

## The AWB-O-Matic Tool

The AWB-O-Matic tool performs the complete "capture and annotate with rectangle" function.

![AWB-O-Matic](awb-o-matic.jpg)

### Usage

Run the application with:
```bash
python awb-o-matic.py -u YOUR_USERNAME
```

The application will try to detect if you are connected to the Pi over ssh, and adjust its preview window accordingly. If this fails, the `--ssh` or `--no-ssh` options can be used to force the correct behaviour (see below)

### Command Line Arguments

- `-u, --user`: Set the user name for saved images (required)
- `-o, --output`: Override the output directory (default: ~/awb-images)
- `-t, --tmp`: Override the temporary directory (default: /dev/shm)
- `-s, --ssh`: Enable SSH mode
- `--no-ssh`: Disable SSH mode

### Basic Workflow

1. First, capture an image. Use the "Capture" button at the top. You can increase or decrease the exposure if necessary with the "EV-" and "EV+" buttons. The captures are saved to a temporary location.
2. Once you have captured an image, we must rename it correctly and copy it to the output folder.
   - If you need to record a grey region for the image, click the "Add Rectangle" button.
   - In the "Add Rectangle" dialog, click and drag the mouse to pan. Use the mouse wheel to zoom. And use Ctrl+Click and drag the mouse to select a rectangular region.
   - If you don't need a grey region, click "Clear Rectangle".
   - You must enter a "Scene Id" to identify this particular scene.
   - Finally click "Rename Image" to rename and copy the images to the output folder.

And return back to step 1 again for the next image.

### Output Files

Images are saved in the output directory with the following naming convention:
```
USER,SENSOR,SCENE_ID,X0,Y0,X1,Y1.jpg
USER,SENSOR,SCENE_ID,X0,Y0,X1,Y1.dng
```

If no rectangle is selected, the coordinates are omitted from the filename.

## The Snapper Tool

The Snapper tool looks quite similar to the AWB-O-Matic tool - with a camera preview and a "Capture" button - but there are no options for annotating the captured images with rectangles. Instead they are written straight to the output folder, with a scene ID that is an incrementing integer.

At a later time, the images can be annotated with grey rectangles as the AWB-O-Matic tool would have done, using the Rectangulator tool.

### Usage

Run the application with:
```bash
python awb-o-snapper.py -u YOUR_USERNAME
```

The application will try to detect if you are connected to the Pi over ssh, and adjust its preview window accordingly. If this fails, the `--ssh` or `--no-ssh` options can be used to force the correct behaviour (see below)

### Command Line Arguments

- `-u, --user`: Set the user name for saved images (required)
- `-o, --output`: Override the output directory (default: ~/awb-captures)
- `--initial-scene-id`: Set the starting scene ID number (default: 0)
- `-s, --ssh`: Enable SSH mode
- `--no-ssh`: Disable SSH mode

### Basic Workflow

Use the "Capture" button to capture images. The "EV-" and "EV+" can be used to change the exposure level if necessary. The scene ID will increase by one every time a picture is taken.

### Output Files

Images are saved in the output directory with the following naming convention:
```
USER,SENSOR,SCENE_ID.jpg
USER,SENSOR,SCENE_ID.dng
```

## The Rectangulator

The Rectangular copies files from an input folder to the output folder, renaming them by appending the grey rectangle coordinates to the filename as the AWB-O-Matic tool would have done. Both JPG and DNG files of each scene are copied.

### Usage

Run the application with:
```bash
python rectangulator.py
```

### Command Line Arguments

- `--input-dir`: Override the input directory (default: ~/awb-captures)
- `--output-dir`: Override the output directory (default: ~/awb-test)

### Basic Workflow

1. Users should double click on one of the files listed to annotate it with a grey rectangle.
  - Images that you've already processed will have a check mark next to them (though check marks are cleared if the tool is stopped and restarted).
2. When the rectangle selection dialog appears, it works in the same way as the AWB-O-Matic tool.
  - Mouse wheel to zoom.
  - Click and drag to pan.
  - Ctrl+Click and drag to select a rectangle.
3. Once a rectangle is selected, the image will be adjusted to make this rectangle _exactly_ grey, allowing you to judge whether this patch is a good choise.
4. If you are happy, click "Accept", otherwise try selecting a different rectangle. Click "Cancel" if you decide not to use this image.

### Output Files

Images are saved in the output directory with the following naming convention:
```
USER,SENSOR,SCENE_ID,X0,Y0,X1,Y1.jpg
USER,SENSOR,SCENE_ID,X0,Y0,X1,Y1.dng
```

## Problems

Please discuss on the Raspberry Pi Camera Forum post.

## License

This project is licensed under the BSD Simplified 2-Clause License - see the [LICENSE](LICENSE) file for details.
