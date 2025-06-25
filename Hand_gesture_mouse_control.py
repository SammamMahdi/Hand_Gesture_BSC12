#!/usr/bin/env python3
# ── Imports ───────────────────────────────────────────────────────────
import math, sys, time, logging, platform, queue, threading, os
from pathlib import Path

# ── USER CONSTANTS ────────────────────────────────────────────────────
SMOOTH_ALPHA = 0.30  # 0 snap  …  1 sluggish
CAMERA_INDEX = 0  # webcam #
CAMERA_MARGIN = 0.10  # 10% margin on each side for easier edge access

# ── Imports / checks ──────────────────────────────────────────────────
try:
    import cv2, mediapipe as mp, pyautogui
    from pynput.mouse import Controller, Button
except ModuleNotFoundError as e:
    sys.exit(f"[ERROR] Missing: {e.name}.  pip install …")

try:
    from PyQt5 import QtWidgets, QtGui, QtCore
except ModuleNotFoundError:
    sys.exit("[ERROR] Missing: PyQt5. pip install PyQt5")


# ── misc helpers ──────────────────────────────────────────────────────
def screen_size():
    return pyautogui.size()


def dist(p1, p2):  # Euclidean
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


# ── Overlay class using PyQt5 ──────────────────────────────────────────
class OverlayWindow(QtWidgets.QWidget):
    # Original colorful fingertip colors from macOS version
    COLORS = {
        (0, 8): (0, 200, 0),  # Index finger - Green
        (0, 12): (0, 0, 230),  # Middle finger - Blue
        (0, 16): (230, 200, 0),  # Ring finger - Yellow
        (0, 20): (230, 0, 150),  # Pinky finger - Pink
    }

    # Fingertip indices (tips of each finger)
    FINGERTIPS = [8, 12, 16, 20]  # Index, Middle, Ring, Pinky tips

    def __init__(self, sw, sh):
        super().__init__(
            None,
            QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Tool,
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.setWindowFlag(QtCore.Qt.Tool)
        self.setGeometry(0, 0, sw, sh)
        self.tips = {}
        self.active_gestures = {}
        self.show()
        self.raise_()  # Ensure window is on top
        self.sw = sw
        self.sh = sh
        print(f"Overlay window created: {sw}x{sh}")

    def update_tips(self, tips, active_gestures=None):
        self.tips = tips
        self.active_gestures = active_gestures or {}
        print(f"Overlay updated with {len(self.tips)} tips: {list(self.tips.keys())}")
        self.update()

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.Antialiasing)

        current_time = time.time()

        print(f"Painting overlay with {len(self.tips)} tips")

        for (hand_idx, lm_idx), pos in self.tips.items():
            # Only show the 4 main fingertips with original colors
            if lm_idx in self.FINGERTIPS:
                # Get original color
                base_color = self.COLORS.get((hand_idx, lm_idx), (200, 200, 200))

                # Check if gesture is active
                is_active = self.active_gestures.get((hand_idx, lm_idx), False)

                # Fingertips - large and prominent like original
                base_radius = 16  # Same as original RADIUS
                alpha = 220

                # Add pulsing effect for active fingertips
                if is_active:
                    pulse = abs(math.sin(current_time * 8)) * 0.4 + 0.6
                    r, g, b = base_color
                    color = QtGui.QColor(
                        int(r * pulse), int(g * pulse), int(b * pulse), alpha
                    )
                    radius = int(base_radius * (1 + 0.3 * pulse))
                else:
                    color = QtGui.QColor(*base_color, alpha)
                    radius = base_radius

                qp.setBrush(color)
                qp.setPen(QtCore.Qt.NoPen)
                x, y = pos
                qp.drawEllipse(QtCore.QPoint(x, y), radius, radius)
                print(f"Drew fingertip {lm_idx} at ({x}, {y}) with color {base_color}")

                # Add labels for fingertips
                fingertip_names = {
                    8: "I",
                    12: "M",
                    16: "R",
                    20: "P",
                }  # Index, Middle, Ring, Pinky
                label = fingertip_names.get(lm_idx, "")
                if label:
                    qp.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
                    qp.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                    qp.drawText(QtCore.QPoint(x + radius + 3, y + 4), label)

                # Add special labels for active gestures
                if is_active and lm_idx in [
                    8,
                    12,
                    16,
                    20,
                ]:  # Index, Middle, Ring, Pinky
                    gesture_names = {8: "MOVE", 12: "GRAB", 16: "RIGHT", 20: "CLICK"}
                    gesture_label = gesture_names.get(lm_idx, "")
                    if gesture_label:
                        qp.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 2))
                        qp.setFont(QtGui.QFont("Arial", 8, QtGui.QFont.Bold))
                        qp.drawText(
                            QtCore.QPoint(x - 20, y - radius - 10), gesture_label
                        )

        qp.end()


# ── Logging & global state ────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s│%(levelname)s│%(message)s")
mouse = Controller()
scr_w, scr_h = screen_size()
logging.info(f"Screen: {scr_w}×{scr_h}")

# ── Shared queue to push fingertip coords to overlay ──────────────────
tip_queue = queue.Queue(maxsize=1)


# ── Mapping helper ────────────────────────────────────────────────────
def map_with_margin(val, margin):
    """Map a value in [0,1] to [0,1] with margin on both sides."""
    val = (val - margin) / (1 - 2 * margin)
    return min(max(val, 0), 1)


# ── Worker thread: camera + Mediapipe + cursor logic ─────────────────
def capture_loop():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        logging.error("Camera not found")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1366)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)
    cam_w, cam_h = int(cap.get(3)), int(cap.get(4))

    hands = mp.solutions.hands.Hands(
        max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.6
    )

    prev_x = prev_y = 0
    middle_grabbed = False
    pinky_was_down = False
    ring_was_down = False
    all_fingers_were_down = False

    show_preview = True

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue
        # frame = cv2.flip(frame,1)  # No flip
        res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        tips_scr = {}
        active_gestures = {}  # Track active gestures for overlay

        if res.multi_hand_landmarks:
            # Use only the first detected hand (like move_cursor.py)
            hand_landmarks = res.multi_hand_landmarks[0]
            lm = hand_landmarks.landmark

            # Get all landmark positions
            landmarks = {
                i: (int(lm[i].x * cam_w), int(lm[i].y * cam_h)) for i in range(21)
            }

            # Pointer follows index finger tip (landmark 8)
            index_tip = lm[8]
            mapped_x = map_with_margin(index_tip.x, CAMERA_MARGIN)
            mapped_y = map_with_margin(index_tip.y, CAMERA_MARGIN)
            cursor_x = int(mapped_x * scr_w)
            cursor_y = int(mapped_y * scr_h)
            smooth_x = int(prev_x + SMOOTH_ALPHA * (cursor_x - prev_x))
            smooth_y = int(prev_y + SMOOTH_ALPHA * (cursor_y - prev_y))
            mouse.position = (smooth_x, smooth_y)
            prev_x, prev_y = smooth_x, smooth_y
            active_gestures[(0, 8)] = True  # Index finger active for movement

            # Middle finger (grab): tip=12, pip=10
            middle_tip = lm[12]
            middle_pip = lm[10]
            # Ring finger (right click): tip=16, pip=14
            ring_tip = lm[16]
            ring_pip = lm[14]
            # Pinky finger (click): tip=20, pip=18
            pinky_tip = lm[20]
            pinky_pip = lm[18]

            # Check if fingers are down (tip below pip)
            middle_down = middle_tip.y > middle_pip.y
            ring_down = ring_tip.y > ring_pip.y
            pinky_down = pinky_tip.y > pinky_pip.y
            index_down = index_tip.y > lm[6].y  # index pip is 6

            # For termination: require strict rock and roll gesture
            CURL_THRESHOLD = 0.04  # adjust as needed
            STRONG_UP_THRESHOLD = 0.04
            index_strong_up = index_tip.y < lm[6].y - STRONG_UP_THRESHOLD
            pinky_strong_up = pinky_tip.y < pinky_pip.y - STRONG_UP_THRESHOLD
            middle_strong_down = middle_tip.y > middle_pip.y + CURL_THRESHOLD
            ring_strong_down = ring_tip.y > ring_pip.y + CURL_THRESHOLD

            # Terminate only if strict rock and roll gesture is detected
            if index_strong_up and pinky_strong_up and middle_strong_down and ring_strong_down:
                if not all_fingers_were_down:
                    print("Rock and roll gesture detected. Exiting...")
                    cap.release()
                    cv2.destroyAllWindows()
                    os._exit(0)
                all_fingers_were_down = True
            else:
                all_fingers_were_down = False

            # Grab with middle finger down
            if middle_down:
                if not middle_grabbed:
                    mouse.press(Button.left)
                    middle_grabbed = True
                active_gestures[(0, 12)] = True
            else:
                if middle_grabbed:
                    mouse.release(Button.left)
                    middle_grabbed = False
                active_gestures[(0, 12)] = False

            # Right click with ring finger down (single click per press)
            if ring_down:
                if not ring_was_down:
                    mouse.press(Button.right)
                    mouse.release(Button.right)
                    ring_was_down = True
                active_gestures[(0, 16)] = True
            else:
                ring_was_down = False
                active_gestures[(0, 16)] = False

            # Click with pinky down (single click per press)
            if pinky_down:
                if not pinky_was_down:
                    mouse.press(Button.left)
                    mouse.release(Button.left)
                    pinky_was_down = True
                active_gestures[(0, 20)] = True
            else:
                pinky_was_down = False
                active_gestures[(0, 20)] = False

            # Convert only the 4 main fingertips to screen coordinates for overlay (like original)
            fingertip_indices = [8, 12, 16, 20]  # Index, Middle, Ring, Pinky
            for i in fingertip_indices:
                if i in lm:
                    mapped_fx = map_with_margin(lm[i].x, CAMERA_MARGIN)
                    mapped_fy = map_with_margin(lm[i].y, CAMERA_MARGIN)
                    tips_scr[(0, i)] = (int(scr_w * mapped_fx), int(scr_h * mapped_fy))

            # Preview draw - show all landmarks
            for i in range(21):
                if i in lm:
                    cx, cy = int(lm[i].x * cam_w), int(lm[i].y * cam_h)
                    # Color code the important fingers
                    if i == 8:  # Index
                        color = (0, 255, 0)  # Green
                    elif i == 12:  # Middle
                        color = (
                            (255, 0, 0) if middle_down else (0, 0, 255)
                        )  # Red if down, Blue if up
                    elif i == 16:  # Ring
                        color = (
                            (255, 0, 255) if ring_down else (255, 255, 0)
                        )  # Magenta if down, Yellow if up
                    elif i == 20:  # Pinky
                        color = (
                            (0, 255, 255) if pinky_down else (255, 255, 0)
                        )  # Cyan if down, Yellow if up
                    else:
                        color = (200, 200, 200)  # Gray for other landmarks
                    cv2.circle(frame, (cx, cy), 8, color, cv2.FILLED)

        # Send tips and active gestures to overlay
        try:
            tip_queue.put_nowait((tips_scr, active_gestures))
        except queue.Full:
            pass

        if show_preview:
            cv2.imshow("Hand Mouse (ESC quits)", frame)
            if cv2.waitKey(1) & 0xFF in (27, 113):
                break  # ESC/q
        else:
            if cv2.waitKey(1) & 0xFF in (27, 113):
                break

    cap.release()
    cv2.destroyAllWindows()
    logging.info("Camera thread ended.")


# ── Boot everything ──────────────────────────────────────────────────────


def main():
    app = QtWidgets.QApplication([])
    overlay = OverlayWindow(scr_w, scr_h)
    print("PyQt5 application started")

    def update_overlay():
        try:
            data = tip_queue.get_nowait()
            if isinstance(data, tuple):
                tips, active_gestures = data
                print(
                    f"Received data: {len(tips)} tips, {len(active_gestures)} active gestures"
                )
            else:
                tips, active_gestures = data, {}
                print(f"Received single data: {len(tips)} tips")
            overlay.update_tips(tips, active_gestures)
        except queue.Empty:
            pass
        QtCore.QTimer.singleShot(16, update_overlay)  # ~60fps

    update_overlay()
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()
    print("Camera thread started")
    app.exec_()
    t.join()


if __name__ == "__main__":
    main()
