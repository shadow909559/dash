"""Real vision recognition: object detection + face recognition (Phase 1).

Everything here runs LOCALLY: an ONNX object detector (YOLO-class, 640x640,
letterboxed) and a face pipeline (DNN face detection + embedding model with
cosine similarity against enrolled persons). No cloud calls, ever.

Honesty contract (docs/ROADMAP.md Phase 1):
- A missing model file is a hard, named state — the service reports WHY it
  cannot see, it never invents detections.
- Every detection carries `backend` ("onnx" | "none") and, when something
  prevented analysis, an honest `reason`.
- Tests inject fake ort sessions; nothing here requires model downloads to
  be tested.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

import numpy as np

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# ── Model management (honest availability) ────────────────────────────────


def vision_models_dir() -> Path:
    """Where ONNX models live. Override with DASH_VISION_MODELS for tests.

    Models have historically landed at two places depending on how the repo
    was fetched: ``apps/models/vision`` (package-relative) and the repo-root
    ``models/vision``. Pick whichever actually exists so a relocated checkout
    doesn't silently disable vision — the honest "models missing" state is
    reserved for genuinely absent files, not path-lottery losers.
    """
    import os

    override = os.environ.get("DASH_VISION_MODELS")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    default = here.parents[3] / "models" / "vision"
    repo_root = here.parents[4] / "models" / "vision"
    if not default.exists() and (repo_root / ModelFiles.DETECTOR).exists():
        return repo_root
    return default


class ModelFiles:
    """Expected model files. The face pair ships as stable artifacts from
    the OpenCV zoo; the object detector is exported from ultralytics YOLO
    (no stable raw download — scripts/fetch_vision_models.py handles it,
    including the export when ultralytics is installed)."""

    DETECTOR = "yolov8n.onnx"
    FACE_DET = "face_detection_yunet_2023mar.onnx"
    FACE_EMB = "face_recognition_sface_2021dec.onnx"

    @classmethod
    def manifest(cls) -> list[dict[str, str]]:
        return [
            {
                "file": cls.DETECTOR,
                "kind": "object-detection",
                "source": "ultralytics yolov8n exported to onnx (export model.py to onnx, opset>=12)",
            },
            {
                "file": cls.FACE_DET,
                "kind": "face-detection",
                "source": "opencv_zoo face_detection_yunet_2023mar.onnx (YuNet, 320x320)",
            },
            {
                "file": cls.FACE_EMB,
                "kind": "face-embedding",
                "source": "opencv_zoo face_recognition_sface_2021dec.onnx (SFace, 128-d, 112x112)",
            },
        ]


def model_status() -> dict[str, Any]:
    """Honest per-model availability + how to get them."""
    d = vision_models_dir()
    models = []
    for m in ModelFiles.manifest():
        p = d / m["file"]
        models.append(
            {
                "file": m["file"],
                "kind": m["kind"],
                "available": p.exists(),
                "source": m.get("source", ""),
            }
        )
    return {
        "models_dir": str(d),
        "models": models,
        "all_available": all(m["available"] for m in models),
        "any_available": any(m["available"] for m in models),
    }


# ── Image decoding ────────────────────────────────────────────────────────

try:  # Pillow is a hard dep (requirements.txt)
    from PIL import Image

    _PIL_OK = True
except ImportError:  # pragma: no cover
    _PIL_OK = False


def decode_to_rgb_array(image_bytes: bytes) -> Optional[np.ndarray]:
    """Decode image bytes to an HxWx3 RGB uint8 array, or None honestly."""
    if not _PIL_OK:
        return None
    try:
        img = Image.open(__import__("io").BytesIO(image_bytes))
        img = img.convert("RGB")
        return np.asarray(img, dtype=np.uint8)
    except Exception:
        return None


# ── Shared plumbing ───────────────────────────────────────────────────────

class _SessionLike(Protocol):
    def run(self, output_names: list[str], feed: dict[str, Any]) -> list[Any]: ...


@dataclass
class Detection:
    """One detected object. `backend` carries the honesty provenance."""

    name: str
    confidence: float
    box: list[int]  # x1, y1, x2, y2 in original-image pixel coords
    backend: str = "onnx"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "confidence": round(self.confidence, 4),
            "box": self.box,
            "backend": self.backend,
        }


@dataclass
class VisionResult:
    """Result of an analysis pass — never fabricated, always provenanced."""

    objects: list[Detection] = field(default_factory=list)
    faces: list[dict[str, Any]] = field(default_factory=list)
    persons: list[dict[str, Any]] = field(default_factory=list)
    backend: str = "none"
    reason: str = ""  # set when nothing could be analyzed, and why

    def to_dict(self) -> dict[str, Any]:
        return {
            "objects": [o.to_dict() for o in self.objects],
            "faces": self.faces,
            "persons": self.persons,
            "backend": self.backend,
            "reason": self.reason,
        }


def _xywh_to_xyxy(box: np.ndarray) -> np.ndarray:
    """YOLOv8 rows are CENTER format (cx, cy, w, h) — convert to corners."""
    cx, cy, w, h = box
    return np.array([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], dtype=np.float32)


def _box_iou(a: np.ndarray, b: np.ndarray) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def nms(boxes: list[np.ndarray], scores: list[float], iou_thr: float = 0.45) -> list[int]:
    """Class-agnostic greedy NMS. Returns kept indices, best-first."""
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    keep: list[int] = []
    for i in order:
        if any(_box_iou(boxes[i], boxes[j]) > iou_thr for j in keep):
            continue
        keep.append(i)
    return keep


# ── Object detector ───────────────────────────────────────────────────────

# Canonical COCO-80 class list, verified against ultralytics
# cfg/datasets/coco.yaml (the class order MUST match yolov8n's training
# indices or detections get mislabeled).
_COCO80 = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
]
_DEFAULT_INPUT = (1, 3, 640, 640)


class ObjectDetectorONNX:
    """YOLO-class ONNX detector. Letterboxed 640x640, NMS post-processing."""

    CONF_THRESHOLD = 0.45
    IOU_THRESHOLD = 0.45

    def __init__(self, model_dir: Optional[Path] = None) -> None:
        self._model_dir = Path(model_dir) if model_dir else vision_models_dir()
        self._session: Optional[_SessionLike] = None
        self._input_name: str = ""
        self._input_hw: tuple[int, int] = _DEFAULT_INPUT[2:]
        self._labels: list[str] = _COCO80
        self._load_error: str = ""
        self._lock = threading.Lock()

    # -- session management --

    def _ensure_session(self) -> bool:
        with self._lock:
            if self._session is not None:
                return True
            path = self._model_dir / ModelFiles.DETECTOR
            if not path.exists():
                self._load_error = (
                    f"object-detector model missing: {path} — run "
                    "scripts/fetch_vision_models.py to download it"
                )
                return False
            try:
                import onnxruntime as ort

                so = ort.SessionOptions()
                so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                sess = ort.InferenceSession(
                    str(path), providers=["CPUExecutionProvider"], sess_options=so
                )
                inp = sess.get_inputs()[0]
                self._input_name = inp.name
                shape = inp.shape
                if isinstance(shape, list) and len(shape) == 4 and isinstance(shape[2], int):
                    self._input_hw = (int(shape[2]), int(shape[3]))
                labels = self._labels
                try:
                    meta = sess.get_modelmeta().custom_metadata_map
                    if "names" in meta:
                        parsed = json.loads(meta["names"])
                        labels = [parsed[k] for k in sorted(parsed, key=int)] if isinstance(parsed, dict) else list(parsed)
                except Exception:
                    pass
                self._labels = labels or _COCO80
                self._session = sess
                self._load_error = ""
                return True
            except Exception as exc:
                self._load_error = f"failed to load {path.name}: {exc}"
                return False

    def _inject_session(self, session: _SessionLike, input_name: str = "images", input_hw: tuple[int, int] = (640, 640), labels: Optional[list[str]] = None) -> None:
        """Test seam: inject a fake ort session (hermetic tests)."""
        self._session = session
        self._input_name = input_name
        self._input_hw = input_hw
        if labels:
            self._labels = labels
        self._load_error = ""

    @property
    def available(self) -> bool:
        return self._ensure_session()

    @property
    def unavailable_reason(self) -> str:
        self._ensure_session()
        return self._load_error

    # -- inference --

    def _letterbox(self, rgb: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        """Resize keeping aspect ratio, pad to input size. Returns (chw, gain, pad)."""
        target_w, target_h = self._input_hw
        h, w = rgb.shape[:2]
        gain = min(target_w / w, target_h / h)
        new_w, new_h = int(w * gain), int(h * gain)
        resized = np.asarray(
            Image.fromarray(rgb).resize((new_w, new_h), Image.BILINEAR)
        )
        pad_w, pad_h = (target_w - new_w) // 2, (target_h - new_h) // 2
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized
        chw = canvas.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        return chw, gain, (pad_w, pad_h)

    def detect(self, rgb: np.ndarray, conf_threshold: Optional[float] = None) -> list[Detection]:
        """Detect objects in an RGB uint8 array. Honest failure: empty + reason."""
        if not self._ensure_session():
            return []
        thr = self.CONF_THRESHOLD if conf_threshold is None else conf_threshold
        chw, gain, (pad_w, pad_h) = self._letterbox(rgb)
        with self._lock:
            outputs = self._session.run(None, {self._input_name: chw})  # type: ignore[union-attr]
        pred = np.asarray(outputs[0])
        if pred.ndim == 3:
            pred = pred[0]
        # Orientation: exports vary between (4+N, anchors) and (anchors, 4+N).
        # Decide by the KNOWN value-axis size (4 + number of classes), not by
        # comparing dims — a size heuristic breaks when anchors < classes+4.
        expected_vals = 4 + len(self._labels)
        if pred.shape[0] == expected_vals and pred.shape[1] != expected_vals:
            pred = pred.T
        if pred.ndim != 2 or pred.shape[1] != expected_vals:
            logger.warning("Unexpected detector output shape %s — skipping frame", pred.shape)
            return []
        boxes_raw, scores_raw, class_ids = [], [], []
        for row in pred:
            cls_scores = row[4:]
            cls_id = int(np.argmax(cls_scores))
            score = float(cls_scores[cls_id])
            if score < thr:
                continue
            boxes_raw.append(_xywh_to_xyxy(row[:4]))
            scores_raw.append(score)
            class_ids.append(cls_id)
        if not boxes_raw:
            return []
        keep = nms(boxes_raw, scores_raw, self.IOU_THRESHOLD)
        out: list[Detection] = []
        h, w = rgb.shape[:2]
        for i in keep:
            x1, y1, x2, y2 = boxes_raw[i]
            # Un-letterbox back to original pixel coords, clamped.
            ox1 = int(max(0, min(w, (x1 - pad_w) / gain)))
            oy1 = int(max(0, min(h, (y1 - pad_h) / gain)))
            ox2 = int(max(0, min(w, (x2 - pad_w) / gain)))
            oy2 = int(max(0, min(h, (y2 - pad_h) / gain)))
            cls_id = class_ids[i]
            name = self._labels[cls_id] if 0 <= cls_id < len(self._labels) else f"class_{cls_id}"
            out.append(Detection(name=name, confidence=scores_raw[i], box=[ox1, oy1, ox2, oy2]))
        out.sort(key=lambda d: d.confidence, reverse=True)
        return out


# ── Face detection + recognition ──────────────────────────────────────────


def _crop_with_margin(rgb: np.ndarray, box: list[int], margin: float = 0.25) -> np.ndarray:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    mx, my = int(w * margin), int(h * margin)
    H, W = rgb.shape[:2]
    cx1, cy1 = max(0, x1 - mx), max(0, y1 - my)
    cx2, cy2 = min(W, x2 + mx), min(H, y2 + my)
    return rgb[cy1:cy2, cx1:cx2]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# Canonical ArcFace/SFace 5-point template (standard OpenCV zoo reference
# coordinates for 112x112): two eyes, nose tip, two mouth corners.
_ARCFACE_DST_LANDMARKS = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def _normalize_landmarks(
    landmarks: Any, frame_w: int, frame_h: int
) -> Optional[list[tuple[float, float]]]:
    """Return 5 usable (x, y) landmark points, or None.

    Usable means: exactly five parseable points, all inside the frame.
    Points slightly outside the detection *box* are fine — YuNet sometimes
    places a corner a pixel outside its own box and the similarity
    transform absorbs that; only frame bounds disqualify.
    """
    if landmarks is None:
        return None
    try:
        pts = [(float(p[0]), float(p[1])) for p in landmarks]
    except (TypeError, ValueError, IndexError):
        return None
    if len(pts) != 5:
        return None
    for x, y in pts:
        if not (0.0 <= x < frame_w and 0.0 <= y < frame_h):
            return None
    return pts


def _align_face(
    rgb: np.ndarray,
    landmarks: list[tuple[float, float]],
    out_size: int = 112,
    padding: float = 0.0,
) -> Optional[np.ndarray]:
    """Similarity-warp a face to the canonical ArcFace 5-point layout.

    A similarity transform (rotate + uniform scale + translate — no
    perspective) maps the detected landmarks onto the standard template,
    so a tilted/distant/close face lands in the same geometry SFace was
    trained on (canonical 5-point transform, no padding by default).
    ``padding`` exists for experimentation only. Returns None only if
    the solver fails.
    """
    try:
        import cv2
    except Exception:  # pragma: no cover - cv2 is a hard dep of this path
        return None
    src = np.asarray(landmarks, dtype=np.float32)
    center = src.mean(axis=0)
    src_padded = center + (src - center) * (1.0 + padding)
    m, _ = cv2.estimateAffinePartial2D(
        src_padded, _ARCFACE_DST_LANDMARKS, method=cv2.LMEDS
    )
    if m is None:
        return None
    return cv2.warpAffine(
        rgb,
        m.astype(np.float32),
        (out_size, out_size),
        flags=cv2.INTER_LINEAR,
        borderValue=0,
    )


@dataclass
class FaceEmbedding:
    person_id: str
    person_name: str
    vector: list[float]


class FaceStore:
    """Enrolled faces persisted as JSON (vectors are not sensitive biometric
    templates in the cloud sense — they stay on this machine regardless)."""

    def __init__(self, store_path: Path) -> None:
        self._path = store_path
        self._lock = threading.Lock()
        self._persons: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._persons = data.get("persons", {})
        except Exception:
            logger.debug("No prior face store loaded", exc_info=True)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({"version": 1, "persons": self._persons}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Face store save failed")

    def list_persons(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "person_id": pid,
                    "name": p["name"],
                    "samples": len(p["embeddings"]),
                    "notify": bool(p.get("notify", True)),
                }
                for pid, p in self._persons.items()
            ]

    def add_sample(self, person_id: str, name: str, vector: list[float]) -> dict[str, Any]:
        with self._lock:
            person = self._persons.get(person_id)
            if person is None:
                person = {"name": name, "embeddings": [], "created_at": datetime.now(timezone.utc).isoformat()}
                self._persons[person_id] = person
            person["embeddings"].append(vector)
            self._save()
            return {"person_id": person_id, "samples": len(person["embeddings"])}

    def remove_person(self, person_id: str) -> bool:
        with self._lock:
            if person_id in self._persons:
                del self._persons[person_id]
                self._save()
                return True
            return False

    def set_notify(self, person_id: str, notify: bool) -> bool:
        """Per-person watcher notification preference (decisions.md #73).

        Stored with the person's enrollment data, so deleting the person
        deletes the preference with it — no orphaned prefs. Returns False
        for an unknown person_id.
        """
        with self._lock:
            person = self._persons.get(person_id)
            if person is None:
                return False
            person["notify"] = bool(notify)
            self._save()
            return True

    def notify_flag(self, person_id: str) -> bool:
        """True unless the person explicitly opted out; unknown → True
        (failing open to notifying, never silently muting someone)."""
        with self._lock:
            person = self._persons.get(person_id)
            if person is None:
                return True
            return bool(person.get("notify", True))

    def all_embeddings(self) -> list[FaceEmbedding]:
        with self._lock:
            return [
                FaceEmbedding(pid, p["name"], list(vec))
                for pid, p in self._persons.items()
                for vec in p["embeddings"]
            ]


MATCH_THRESHOLD = 0.50  # cosine similarity between embeddings
# Tuned for SFace (OpenCV uses ~0.363 for verification; 0.50 is stricter to
# avoid false IDs). Override with DASH_FACE_MATCH_THRESHOLD.
_PERSON_ID_MAX = 64

_YUNET_LOCK = threading.Lock()  # FaceDetectorYN holds internal state; serialize


class _FaceDetector:
    """Adapter over cv2.FaceDetectorYN implementing the decoded-face seam:
    detect_faces(rgb) -> [{"box": [x1,y1,x2,y2], "confidence": float}].

    Also the injection point for hermetic fakes: a fake with the same
    detect_faces() method can replace this entirely.
    """

    CONF_THRESHOLD = 0.6

    def __init__(self, yunet: Any) -> None:
        self.yunet = yunet

    def detect_faces(self, rgb: np.ndarray) -> list[dict[str, Any]]:
        h, w = rgb.shape[:2]
        # FaceDetectorYN must be sized to the actual frame; resizing inputs
        # ourselves would misplace boxes relative to the embeddings' crops.
        self.yunet.setInputSize((w, h))
        with self._lock_detection():
            _, faces = self.yunet.detect(rgb)
        if faces is None:
            return []
        out: list[dict[str, Any]] = []
        for row in np.asarray(faces):
            conf = float(row[14])
            if conf < self.CONF_THRESHOLD:
                continue
            x, y, fw, fh = (float(v) for v in row[:4])
            # YuNet rows carry the 5 landmarks at row[4:14]: two eyes, nose
            # tip, two mouth corners. They feed SFace similarity alignment.
            lm = row[4:14].reshape(5, 2)
            out.append(
                {
                    "box": [
                        int(max(0, x)),
                        int(max(0, y)),
                        int(min(w, x + fw)),
                        int(min(h, y + fh)),
                    ],
                    "confidence": round(conf, 4),
                    "landmarks": [(float(px), float(py)) for px, py in lm],
                }
            )
        out.sort(key=lambda f: f["confidence"], reverse=True)
        return out

    def _lock_detection(self):
        # FaceDetectorYN holds internal state (input size); serialize uses.
        return _YUNET_LOCK


class FaceRecognitionService:
    """Detect faces, embed them, match against enrolled persons — or say so."""

    EMBED_SIZE = 128  # SFace output dim (an ArcFace swap would be 512; the
    # pipeline reads the real output shape, this is documentation only)

    def __init__(self, model_dir: Optional[Path] = None, store_path: Optional[Path] = None) -> None:
        self._model_dir = Path(model_dir) if model_dir else vision_models_dir()
        store_path = store_path or (self._model_dir / "known_faces.json")
        self._store = FaceStore(store_path)
        self._det_session: Optional[_SessionLike] = None
        self._det: Optional[Any] = None  # cv2.FaceDetectorYN (or fake) — the seam
        self._emb_session: Optional[_SessionLike] = None
        self._emb_input_size = 112
        self._errors: dict[str, str] = {}
        self._lock = threading.Lock()
        import os

        try:
            self._threshold = float(os.environ.get("DASH_FACE_MATCH_THRESHOLD", str(MATCH_THRESHOLD)))
        except ValueError:
            self._threshold = MATCH_THRESHOLD

    # -- store passthrough --

    def list_persons(self) -> list[dict[str, Any]]:
        return self._store.list_persons()

    def set_person_notify(self, person_id: str, notify: bool) -> bool:
        return self._store.set_notify(person_id, notify)

    def person_notify_flag(self, person_id: str) -> bool:
        return self._store.notify_flag(person_id)

    def remove_person(self, person_id: str) -> bool:
        return self._store.remove_person(person_id)

    # -- session management (same honest availability pattern) --

    def _ensure_sessions(self) -> bool:
        with self._lock:
            if self._det_session is not None and self._emb_session is not None:
                return True
            det_path = self._model_dir / ModelFiles.FACE_DET
            emb_path = self._model_dir / ModelFiles.FACE_EMB
            self._errors = {}
            if not det_path.exists():
                self._errors["detector"] = f"face-detector model missing: {det_path}"
            if not emb_path.exists():
                self._errors["embedder"] = f"face-embedding model missing: {emb_path}"
            if self._errors:
                return False
            try:
                import onnxruntime as ort

                self._emb_session = ort.InferenceSession(str(emb_path), providers=["CPUExecutionProvider"])
                # The feed key must be the embedder's OWN input name — the
                # old code hardcoded SFace's "input.1" everywhere, which is
                # also how the YuNet mismatch hid (decisions.md #58 follow-up).
                self._emb_input_name = self._emb_session.get_inputs()[0].name  # type: ignore[union-attr]
                # Face DETECTION goes through OpenCV's reference
                # implementation (cv2.FaceDetectorYN): the fetched YuNet
                # ONNX has three raw outputs (loc/conf/iou) that need the
                # official anchor decode — the previous hand-rolled decoder
                # assumed a post-processed layout the raw model never
                # produces (found live, zidane.jpg). Faces are also fed at
                # their native resolution — no letterbox guessing.
                self._det = self._load_face_detector(det_path)
                self._det_session = self._det.yunet  # type: ignore[union-attr]
                return True
            except Exception as exc:
                self._errors["load"] = str(exc)
                return False

    def _load_face_detector(self, det_path: Path) -> Any:
        """Create the YuNet face detector via OpenCV's reference wrapper.

        Raises (honest failure) when cv2 lacks FaceDetectorYN — there is no
        working fallback decoder to pretend with.
        """
        try:
            import cv2

            if not hasattr(cv2, "FaceDetectorYN"):
                raise RuntimeError("cv2 has no FaceDetectorYN — update opencv-python")
            yunet = cv2.FaceDetectorYN.create(
                str(det_path), "", (320, 320), 0.6, 0.3, 5000
            )
        except Exception as exc:
            raise RuntimeError(f"face detector unavailable: {exc}") from exc

        wrapper = _FaceDetector(yunet)
        return wrapper

    def _inject_sessions(self, det: Optional[_SessionLike], emb: Optional[_SessionLike], det_hw: tuple[int, int] = (320, 320), emb_size: int = 112) -> None:
        """Test seam: inject a fake FACE DETECTOR and fake embedder session.

        The detector seam is the decoded-face boundary (returns
        [{"box", "confidence"}]), matching _detect_faces' contract.
        `det=None` injects "detector unavailable".
        """
        if det is not None:
            if hasattr(det, "detect_faces"):
                self._det = det  # fake implementing the decoded-face seam
            else:
                self._det = _FaceDetector(det)
            self._det_session = getattr(det, "yunet", det)
            self._errors.pop("detector", None)
            self._errors.pop("load", None)
        else:
            self._det, self._det_session = None, None
            self._errors["detector"] = "injected: face detector unavailable"
        self._emb_session = emb
        self._emb_input_size = emb_size
        if emb is not None:
            self._emb_input_name = getattr(emb, "input_name", "") or "input.1"
            self._errors.pop("embedder", None)
            self._errors.pop("load", None)

    @property
    def available(self) -> bool:
        return self._ensure_sessions()

    def unavailable_reasons(self) -> dict[str, str]:
        self._ensure_sessions()
        return dict(self._errors)

    # -- embedding --

    def _aligned_embedding(
        self, rgb: np.ndarray, box: list[int], landmarks: Any = None
    ) -> Optional[np.ndarray]:
        """Embed one face.

        With 5 valid landmarks: similarity-warp to the canonical ArcFace
        layout — the geometry SFace was trained on — making embeddings
        invariant to head tilt, roll, and distance. Without usable
        landmarks: legacy margin-crop fallback (honestly flagged by
        callers via the face entry's ``landmark_aligned`` field).
        """
        face: Optional[np.ndarray] = None
        pts = _normalize_landmarks(landmarks, rgb.shape[1], rgb.shape[0])
        if pts is not None:
            face = _align_face(rgb, pts, self._emb_input_size)
        if face is None:
            face = _crop_with_margin(rgb, box)
        if face.size == 0:
            return None
        size = self._emb_input_size
        img = np.asarray(Image.fromarray(face).resize((size, size), Image.BILINEAR))
        chw = img.astype(np.float32).transpose(2, 0, 1)[None]
        # The zoo SFace ONNX expects RAW 0-255 RGB — no normalization. The
        # ArcFace-style (x-127.5)/128 scaling previously used here starved
        # the model (feature norm ~2.2 vs ~12.8 reference; every face
        # correlated ~0.93 with every other — decisions.md #61/#68).
        # Verified against cv2.FaceRecognizerSF on the same crops (cos 1.0).
        with self._lock:
            outputs = self._emb_session.run(None, {self._emb_input_name or "input.1": chw})  # type: ignore[union-attr]
        vec = np.asarray(outputs[0]).reshape(-1)
        if vec.size == 0:
            return None
        return vec

    # -- public API --

    def enroll(self, rgb: np.ndarray, name: str, person_id: Optional[str] = None) -> dict[str, Any]:
        """Enroll the single clearest face in the frame under `name`."""
        if not name or not name.strip():
            return {"ok": False, "reason": "name is required"}
        if not self._ensure_sessions():
            return {"ok": False, "reason": "face models unavailable: " + "; ".join(f"{k}: {v}" for k, v in self._errors.items())}
        faces = self._detect_faces(rgb)
        if not faces:
            return {"ok": False, "reason": "no face detected in the frame"}
        # Enroll the highest, then largest box (closest to camera).
        faces.sort(key=lambda f: (f["box"][3] - f["box"][1]), reverse=True)
        box = faces[0]["box"]
        vec = self._aligned_embedding(rgb, box, faces[0].get("landmarks"))
        if vec is None:
            return {"ok": False, "reason": "embedding failed for the detected face"}
        pid = (person_id or "").strip()[:_PERSON_ID_MAX] or f"person_{abs(hash(name.strip().lower())) % 10**10:010d}"
        entry = self._store.add_sample(pid, name.strip(), [float(v) for v in vec])
        return {"ok": True, "person_id": pid, "name": name.strip(), "samples": entry["samples"]}

    def _detect_faces(self, rgb: np.ndarray) -> list[dict[str, Any]]:
        """Face boxes via cv2.FaceDetectorYN (OpenCV's YuNet reference)."""
        if self._det is None:
            if self._det_session is None:
                raise RuntimeError("face detector not initialized")
            self._det = self._load_face_detector(
                self._model_dir / ModelFiles.FACE_DET
            )
        return self._det.detect_faces(rgb)

    def analyze_frame(self, rgb: np.ndarray, include_objects: Optional[ObjectDetectorONNX] = None) -> VisionResult:
        """One pass: faces + enrolled-person matches (+ objects if detector given).

        Honest by construction: unmodelled backend = reason set, empty lists.
        """
        result = VisionResult()
        if not self._ensure_sessions():
            result.reason = "; ".join(f"{k}: {v}" for k, v in self._errors.items())
            return result
        faces = self._detect_faces(rgb)
        result.backend = "onnx"
        embeddings = self._store.all_embeddings()
        for f in faces:
            vec = self._aligned_embedding(rgb, f["box"], f.get("landmarks"))
            match = None
            if vec is not None and embeddings:
                best, best_sim = None, -1.0
                for fe in embeddings:
                    sim = _cosine(vec, np.asarray(fe.vector, dtype=np.float32))
                    if sim > best_sim:
                        best, best_sim = fe, sim
                if best_sim >= self._threshold:
                    match = {"person_id": best.person_id, "name": best.person_name, "similarity": round(best_sim, 4)}
            entry = {
                "box": f["box"],
                "confidence": f["confidence"],
                "match": match,
                # Honest provenance: did this embedding come from landmark
                # alignment or the margin-crop fallback?
                "landmark_aligned": _normalize_landmarks(
                    f.get("landmarks"), rgb.shape[1], rgb.shape[0]
                )
                is not None,
            }
            if match is None:
                entry["match_status"] = "unknown person" if embeddings else "no persons enrolled"
            result.faces.append(entry)
            if match is not None:
                result.persons.append({**match, "box": f["box"]})
        if include_objects is not None:
            result.objects = include_objects.detect(rgb)
        return result


# ── Singletons ────────────────────────────────────────────────────────────

_object_detector: Optional[ObjectDetectorONNX] = None
_face_service: Optional[FaceRecognitionService] = None


def get_object_detector() -> ObjectDetectorONNX:
    global _object_detector
    if _object_detector is None:
        _object_detector = ObjectDetectorONNX()
    return _object_detector


def get_face_service() -> FaceRecognitionService:
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService()
    return _face_service
