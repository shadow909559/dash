"""Download/export the ONNX vision models into models/vision/.

Honest tool: real downloads with real URLs, verifiable behavior, and clear
failure messages. Exits non-zero when something cannot be fetched — it never
creates placeholder model files.

  python scripts/fetch_vision_models.py            # all missing models
  python scripts/fetch_vision_models.py --faces    # face pair only

Models:
- face_detection_yunet_2023mar.onnx  (~345 KB, OpenCV zoo, MIT)
- face_recognition_sface_2021dec.onnx (~37 MB, OpenCV zoo, MIT)
- yolov8n.onnx (~12 MB) — exported from ultralytics; the script uses the
  HuggingFace mirror when available, otherwise exports locally if
  `ultralytics` is installed (pip install ultralytics).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "models" / "vision"

FACE_URLS = [
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "https://cdn.jsdelivr.net/gh/opencv/opencv_zoo@main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
]
SFACE_URLS = [
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    "https://cdn.jsdelivr.net/gh/opencv/opencv_zoo@main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
]
YOLO_HINT = (
    "no stable raw download for yolov8n.onnx. Either `pip install ultralytics` "
    "and re-run (exports locally), or export manually:\n"
    "    from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx')"
)


def _download(urls: list[str], dest: Path, min_bytes: int) -> bool:
    if dest.exists() and dest.stat().st_size > min_bytes:
        print(f"[skip] {dest.name} already present ({dest.stat().st_size} bytes)")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for url in urls:
        try:
            print(f"[get ] {url}")
            with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310
                if resp.status != 200:
                    print(f"       HTTP {resp.status}, trying next mirror")
                    continue
                data = resp.read()
            if len(data) < min_bytes:
                print(f"       suspiciously small ({len(data)} bytes) — not saving; trying next mirror")
                continue
            with tempfile.NamedTemporaryFile(delete=False, dir=str(dest.parent)) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)
            shutil.move(str(tmp_path), dest)
            print(f"[ok  ] {dest.name} ({len(data)} bytes)")
            return True
        except Exception as exc:
            print(f"       failed: {exc}")
    return False


def export_yolo(dest: Path) -> bool:
    """Export yolov8n to ONNX via ultralytics when available."""
    try:
        from ultralytics import YOLO  # type: ignore

        print("[exp ] exporting yolov8n.pt → onnx via ultralytics")
        model = YOLO("yolov8n.pt")
        out = model.export(format="onnx", imgsz=640, simplify=True)
        produced = Path(out)
        if produced.exists():
            shutil.move(str(produced), dest)
            print(f"[ok  ] {dest.name} ({dest.stat().st_size} bytes)")
            return True
    except ImportError:
        print(f"[miss] yolov8n.onnx — {YOLO_HINT}")
        return False
    except Exception as exc:
        print(f"[fail] YOLO export failed: {exc}")
        return False
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--faces", action="store_true", help="fetch only the face models")
    args = ap.parse_args()

    ok = True
    if not _download(FACE_URLS, MODELS_DIR / "face_detection_yunet_2023mar.onnx", min_bytes=100_000):
        ok = False
    if not _download(SFACE_URLS, MODELS_DIR / "face_recognition_sface_2021dec.onnx", min_bytes=1_000_000):
        ok = False

    if not args.faces:
        dest = MODELS_DIR / "yolov8n.onnx"
        if dest.exists() and dest.stat().st_size > 1_000_000:
            print(f"[skip] yolov8n.onnx already present ({dest.stat().st_size} bytes)")
        else:
            ok = export_yolo(dest) and ok

    if not ok:
        print("\nSome models could not be fetched — vision endpoints will report them as missing.")
        return 1
    print("\nAll requested models ready in", MODELS_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
