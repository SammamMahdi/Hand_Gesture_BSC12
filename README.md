# Hand_Gesture_BSC12

This program turns your hand into a mouse using your webcam. 
It tracks your hand and fingertips, allowing you to control the mouse cursor and perform clicks with simple finger gestures. 
A transparent overlay shows your fingertip positions in real time.

## Features
- Move the mouse cursor with your index finger.
- Left-click by pressing your pinky finger down.
- Drag (grab) by pressing and holding your middle finger down.
- Right-click by pressing your ring finger down.
- Terminate the program by pressing all 5 fingers down.
- Visual overlay displays fingertip positions and gesture status.

*Note: For best results, keep your fingers straight and only bend them when you want to perform a gesture.*

## Requirements
- Windows OS
- Python 3.7+
- Webcam
- Required Python libraries:

  ```sh
  pip install opencv-python mediapipe pyautogui pynput PyQt5
  ```

## Installation & Setup
1. **Connect your webcam** to your computer and make sure it is working.
2. **Install Python 3.7 or newer** if you haven't already.
3. **Open a terminal or command prompt** in the folder containing this project.
4. **Install the required libraries** by running:
   ```sh
   pip install opencv-python mediapipe pyautogui pynput PyQt5
   ```

## Usage
5. **Run the script** with:
   ```sh
   python Hand_gesture_mouse_control.py
   ```
   or just run the script in your IDE.
6. **A preview window will open** showing your webcam feed. A transparent overlay will appear on your desktop showing colored dots for your fingertips.

## Gestures
- **Move:** Move your index finger to move the cursor.
- **Left Click:** Tap your pinky finger down.
- **Drag/Grab:** Hold your middle finger down to grab (hold left mouse button).
- **Right Click:** Tap your ring finger down.
- **Terminate:** Press all 5 fingers down.
- **To quit:** Press `ESC` or `q` in the preview window or press all 5 fingers down.

## Troubleshooting
- If you see an error about missing modules, install them with pip as shown above.
- If the overlay does not appear, ensure PyQt5 is installed and your system supports transparent windows.
- If the camera is not detected, check your webcam connection and CAMERA_INDEX setting in the script.

## Customization
- Adjust sensitivity and smoothing by changing the `SMOOTH_ALPHA` constant in the script.
- Change the camera by setting `CAMERA_INDEX` in the script.
- Edit colors and overlay appearance in the `OverlayWindow` class.

---

Edit the constants in the script to tweak behaviour as needed. 
