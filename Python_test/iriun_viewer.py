#!/usr/bin/env python3
"""Display the video stream from Iriun Webcam (Android) on screen.

Iriun uses a proprietary protocol, so the phone talks to the Iriun Webcam
desktop app, which exposes the stream as a virtual webcam. This script reads
that virtual webcam with OpenCV.

Setup:
    pip install opencv-python
    1. Install "Iriun Webcam" on the PC: https://iriun.com
    2. Start the desktop app and the Android app (same Wi-Fi, or USB).
    3. Run:  python iriun_viewer.py            (auto-detect)
             python iriun_viewer.py --list     (list cameras)
             python iriun_viewer.py --index 1  (force a camera index)

Keys: q or ESC = quit, f = toggle fullscreen, s = save screenshot.
"""
import argparse
import platform
import sys
import time

import cv2


def backend():
    system = platform.system()
    if system == "Windows":
        return cv2.CAP_DSHOW
    if system == "Darwin":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_V4L2


def open_camera(index):
    cap = cv2.VideoCapture(index, backend())
    if not cap.isOpened():
        cap.release()
        return None
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        return None
    return cap


def list_cameras(max_index=10):
    found = []
    for i in range(max_index):
        cap = open_camera(i)
        if cap is not None:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            found.append((i, w, h))
            cap.release()
    return found


def main():
    parser = argparse.ArgumentParser(description="View the Iriun Webcam stream")
    parser.add_argument("--index", type=int, help="camera index to use")
    parser.add_argument("--list", action="store_true", help="list cameras and exit")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()

    if args.list:
        cams = list_cameras()
        if not cams:
            print("No camera found.")
        for i, w, h in cams:
            print(f"Camera {i}: {w}x{h}")
        return

    if args.index is not None:
        indices = [args.index]
    else:
        indices = [i for i, _, _ in list_cameras()]
        if not indices:
            sys.exit("No camera found. Is the Iriun Webcam desktop app running "
                     "and the phone connected?")
        if len(indices) > 1:
            print(f"Cameras found: {indices}. Using the last one (virtual "
                  "cameras like Iriun usually come last). Use --index to change.")
            indices = [indices[-1]]

    cap = open_camera(indices[0])
    if cap is None:
        sys.exit(f"Could not open camera {indices[0]}.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    win = "Iriun stream"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    fullscreen = False
    last, fps = time.time(), 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Lost the stream.")
            break

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - last, 1e-6))
        last = now
        cv2.putText(frame, f"{fps:4.1f} FPS", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow(win, frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("f"):
            fullscreen = not fullscreen
            cv2.setWindowProperty(
                win, cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
        if key == ord("s"):
            name = time.strftime("iriun_%Y%m%d_%H%M%S.png")
            cv2.imwrite(name, frame)
            print("Saved", name)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
