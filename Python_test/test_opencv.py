import argparse
import platform
import sys
import time

import cv2
import numpy as np


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


def find_cameras(max_index=10):
    found = []
    for i in range(max_index):
        cap = open_camera(i)
        if cap is not None:
            found.append(i)
            cap.release()
    return found


def get_dictionary(name):
    aruco = cv2.aruco
    if not hasattr(aruco, name):
        sys.exit(f"Unknown dictionary '{name}'. Example: DICT_4X4_50, DICT_6X6_250")
    dict_id = getattr(aruco, name)
    if hasattr(aruco, "getPredefinedDictionary"):
        return aruco.getPredefinedDictionary(dict_id)
    return aruco.Dictionary_get(dict_id)


def make_detector(dictionary):
    """Return detect(gray) -> (corners, ids) for both new and old OpenCV APIs."""
    aruco = cv2.aruco
    if hasattr(aruco, "ArucoDetector"):  # OpenCV >= 4.7
        detector = aruco.ArucoDetector(dictionary, aruco.DetectorParameters())

        def detect(gray):
            corners, ids, _ = detector.detectMarkers(gray)
            return corners, ids
    else:  # older versions
        params = aruco.DetectorParameters_create()

        def detect(gray):
            corners, ids, _ = aruco.detectMarkers(gray, dictionary, parameters=params)
            return corners, ids

    return detect


def make_marker_image(dictionary, marker_id, size=600):
    aruco = cv2.aruco
    if hasattr(aruco, "generateImageMarker"):
        img = aruco.generateImageMarker(dictionary, marker_id, size)
    else:
        img = aruco.drawMarker(dictionary, marker_id, size)
    return cv2.copyMakeBorder(img, 50, 50, 50, 50, cv2.BORDER_CONSTANT, value=255)


def draw_cube(frame, rvec, tvec, K, dist, size):
    """Draw a cube standing on the marker (base = marker square)."""
    s = size / 2.0
    pts = np.float32([
        [-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0],              # base
        [-s, s, size], [s, s, size], [s, -s, size], [-s, -s, size],  # top
    ])
    img_pts, _ = cv2.projectPoints(pts, rvec, tvec, K, dist)
    p = img_pts.reshape(-1, 2).astype(int)

    # filled translucent top face
    overlay = frame.copy()
    cv2.fillConvexPoly(overlay, p[4:8], (0, 200, 255))
    cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)

    for i in range(4):
        cv2.line(frame, tuple(p[i]), tuple(p[(i + 1) % 4]), (255, 0, 0), 3)          # base
        cv2.line(frame, tuple(p[i]), tuple(p[i + 4]), (0, 255, 0), 3)                # pillars
        cv2.line(frame, tuple(p[4 + i]), tuple(p[4 + (i + 1) % 4]), (0, 0, 255), 3)  # top


def main():
    parser = argparse.ArgumentParser(description="Iriun + ArUco + 3D cube")
    parser.add_argument("--index", type=int, help="camera index")
    parser.add_argument("--dict", default="DICT_4X4_50", help="ArUco dictionary")
    parser.add_argument("--marker-size", type=float, default=0.05,
                        help="marker side length in meters (default 0.05)")
    parser.add_argument("--calib", help=".npz with camera_matrix and dist_coeffs")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--make-marker", type=int, metavar="ID",
                        help="write marker_<ID>.png and exit")
    args = parser.parse_args()

    if not hasattr(cv2, "aruco"):
        sys.exit("cv2.aruco missing. Install with: pip install opencv-contrib-python "
                 "(or a recent opencv-python)")

    dictionary = get_dictionary(args.dict)

    if args.make_marker is not None:
        name = f"marker_{args.make_marker}.png"
        cv2.imwrite(name, make_marker_image(dictionary, args.make_marker))
        print("Wrote", name)
        return

    if args.index is not None:
        index = args.index
    else:
        cams = find_cameras()
        if not cams:
            sys.exit("No camera found. Is the Iriun Webcam desktop app running?")
        index = cams[-1]
        if len(cams) > 1:
            print(f"Cameras found: {cams}. Using {index}. Use --index to change.")

    cap = open_camera(index)
    if cap is None:
        sys.exit(f"Could not open camera {index}.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    ok, frame = cap.read()
    h, w = frame.shape[:2]

    if args.calib:
        data = np.load(args.calib)
        K, dist = data["camera_matrix"], data["dist_coeffs"]
        print("Loaded calibration from", args.calib)
    else:
        K = np.array([[w, 0, w / 2], [0, w, h / 2], [0, 0, 1]], dtype=np.float64)
        dist = np.zeros((5, 1))
        print("No calibration file: using an approximate camera model.")

    detect = make_detector(dictionary)
    ms = args.marker_size
    marker_pts = np.float32([
        [-ms / 2, ms / 2, 0], [ms / 2, ms / 2, 0],
        [ms / 2, -ms / 2, 0], [-ms / 2, -ms / 2, 0],
    ])

    win = "Iriun ArUco cube"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Lost the stream.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids = detect(gray)

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            for c, mid in zip(corners, ids.flatten()):
                img_pts = c.reshape(4, 2).astype(np.float32)
                ok_pnp, rvec, tvec = cv2.solvePnP(
                    marker_pts, img_pts, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)
                if ok_pnp:
                    draw_cube(frame, rvec, tvec, K, dist, ms)
                    cv2.drawFrameAxes(frame, K, dist, rvec, tvec, ms * 0.75)

        cv2.imshow(win, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("s"):
            name = time.strftime("aruco_%Y%m%d_%H%M%S.png")
            cv2.imwrite(name, frame)
            print("Saved", name)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
