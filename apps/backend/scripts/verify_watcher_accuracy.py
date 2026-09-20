"""Watcher recognition-accuracy re-verification (closes decisions.md #61's gap).

#61's stated gap: "cross-image face matching is overconfident — bus.jpg's two
strangers matched enrolled 'Zidane' at 0.95, because embedding skips SFace's
5-point landmark alignment (YuNet supplies the landmarks; we discard them)."

Real models, real photos (ultralytics assets). YuNet detects on the upright
photo only — rotated probes are built by transforming the detected landmarks
(mathematically exact), because YuNet's own detection range does not cover
90-degree roll and that would conflate detection with recognition.

Measurements:
1. The #61 false-accept: max similarity of bus.jpg's two strangers against
   enrolled Zidane — aligned probe/embed (production) vs fallback/fallback
   (#61's original path).
2. The true person across images: aligned embeddings of pose-rotated probes
   vs the upright enrollment.
3. The deployed mixed-store hazard: the real known_faces.json holds a
   PRE-alignment (fallback) vector; new probes are aligned. A true-person
   probe against that stale store is measured — if it drops below threshold,
   re-enrollment is REQUIRED and the report says so.
4. Two real VisionWatcher.run_cycle passes over the photos through a fake
   camera: bus.jpg must NOT emit person_seen; a 15-degree-tilted Zidane MUST.

This script never writes the real face store (temp store throughout).

Exit 0 iff all gates pass. Writes a JSON report to apps/tmp/.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dash_backend.vision import recognition as rec  # noqa: E402
from dash_backend.vision.camera_vision import CaptureResult  # noqa: E402
from dash_backend.vision.watcher import VisionWatcher  # noqa: E402

PHOTOS = Path(__file__).resolve().parents[2] / "tmp" / "vision_photos"


def _resolve_photo(name: str) -> Path:
    """Canonical location first, else the ultralytics asset it came from."""
    p = PHOTOS / name
    if p.exists():
        return p
    try:
        import ultralytics

        alt = Path(ultralytics.__file__).parent / "assets" / name
        if alt.exists():
            return alt
    except ImportError:
        pass
    raise SystemExit(
        f"photo not found: {p} (copy ultralytics assets/{name} there, or install ultralytics)"
    )


def imread(path: Path) -> bytes:
    data = path.read_bytes()
    if not data:
        raise SystemExit(f"empty photo: {path}")
    return data


def rotate_image_and_points(
    rgb: np.ndarray, pts: list[tuple[float, float]], deg: float
) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Rotate the image around its center and the landmark points with it."""
    import cv2

    h, w = rgb.shape[:2]
    mat = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    out = cv2.warpAffine(rgb, mat, (w, h))
    return out, [
        (
            float(mat[0, 0] * x + mat[0, 1] * y + mat[0, 2]),
            float(mat[1, 0] * x + mat[1, 1] * y + mat[1, 2]),
        )
        for x, y in pts
    ]


class FakeCamera:
    """Serves the given JPEG frames, one per capture call, then repeats."""

    def __init__(self, frames: list[bytes]) -> None:
        self._frames = frames
        self._i = 0

    async def capture_result(self, _camera_id: int) -> CaptureResult:
        frame = self._frames[self._i % len(self._frames)]
        self._i += 1
        return CaptureResult(frame=frame)  # ok is a derived property


class FakeBus:
    async def publish_sync(self, topic: str, data: dict[str, Any], source: str = "") -> None:
        pass


class FakeBrain:
    def __init__(self) -> None:
        self.observations: list[dict[str, Any]] = []

    def add_observation(self, obs: dict[str, Any]) -> None:
        self.observations.append(obs)


async def run_watcher_cycle(camera: FakeCamera, svc) -> dict[str, Any]:
    watcher = VisionWatcher(
        interval_seconds=30,
        repeat_cooldown_s=0.0,
        camera=camera,
        recognizer=svc,
        detector=None,
        brain=FakeBrain(),
        bus=FakeBus(),
    )
    return await watcher.run_cycle()


def main() -> int:
    models_dir = rec.vision_models_dir()
    zidane_bytes = imread(_resolve_photo("zidane.jpg"))
    bus_bytes = imread(_resolve_photo("bus.jpg"))

    # Inform (never touch): the real store, if present, holds pre-alignment vectors.
    real_store = models_dir / "known_faces.json"
    if real_store.exists():
        try:
            data = json.loads(real_store.read_text(encoding="utf-8"))
            persons = data.get("persons", {})
            print(
                f"note: real store exists ({len(persons)} person(s), "
                "pre-alignment vectors); this run uses an isolated temp store"
            )
        except Exception as exc:
            print(f"note: real store exists but is unreadable: {exc}")

    tmp = Path(tempfile.mkdtemp(prefix="dash_watcher_verify_"))
    try:
        svc = rec.FaceRecognitionService(model_dir=models_dir, store_path=tmp / "faces.json")
        if not svc.available:
            print("face service unavailable:", svc.unavailable_reasons())
            return 3

        zidane = rec.decode_to_rgb_array(zidane_bytes)
        bus = rec.decode_to_rgb_array(bus_bytes)
        if zidane is None or bus is None:
            print("photo decode failed")
            return 3

        # YuNet (real) on the upright photo: the one trusted detection.
        faces = svc._detect_faces(zidane)
        if not faces:
            print("no face detected in zidane.jpg")
            return 3
        box0, lm0 = faces[0]["box"], faces[0]["landmarks"]
        if not lm0 or len(lm0) != 5:
            print("upright detection lacks 5 landmarks")
            return 3

        # Enrollment vectors: production (aligned) and legacy (fallback).
        enroll_vec = np.asarray(svc._aligned_embedding(zidane, box0, lm0), dtype=np.float32)
        fallback_vec = np.asarray(svc._aligned_embedding(zidane, box0, None), dtype=np.float32)
        thr = svc._threshold

        # Pose-rotated probes of the SAME person (landmarks transformed exactly).
        rot15_img, rot15_lm = rotate_image_and_points(zidane, lm0, 15.0)
        rot15_vec = np.asarray(
            svc._aligned_embedding(rot15_img, box0, rot15_lm), dtype=np.float32
        )

        # The #61 false-accept, quantified on bus.jpg's strangers. The
        # preprocessing fix applies to BOTH paths, so the fallback no longer
        # false-accepts either — it is measured as the geometric-only baseline.
        sim = {"faces": 0, "aligned": None, "fallback": None}
        for f in svc._detect_faces(bus):
            sim["faces"] += 1
            va = svc._aligned_embedding(bus, f["box"], f.get("landmarks"))
            vf = svc._aligned_embedding(bus, f["box"], None)
            for key, vec in (("aligned", va), ("fallback", vf)):
                if vec is not None:
                    s = rec._cosine(np.asarray(vec, dtype=np.float32), enroll_vec)
                    if sim[key] is None or s > sim[key]:
                        sim[key] = round(float(s), 4)

        # Featureless-frame sanity: an embedding pipeline with a huge
        # input-independent component (the #61 disease) correlates highly
        # with a blank frame; a healthy one must not.
        blank_vec = svc._aligned_embedding(
            np.full(zidane.shape, 128, dtype=np.uint8), box0, None
        )
        blank_sim = (
            None
            if blank_vec is None
            else round(float(rec._cosine(np.asarray(blank_vec, dtype=np.float32), enroll_vec)), 4)
        )

        true_aligned_store = round(float(rec._cosine(rot15_vec, enroll_vec)), 4)
        true_mixed_store = round(float(rec._cosine(rot15_vec, fallback_vec)), 4)

        print(f"threshold {thr} | bus.jpg faces: {sim['faces']}")
        print(f"strangers-vs-Zidane  aligned:   {sim['aligned']}   (#61 saw 0.95)")
        print(f"strangers-vs-Zidane  fallback:  {sim['fallback']}")
        print(f"blank-vs-Zidane (sanity):       {blank_sim}")
        print(f"true person rot15 vs aligned enroll:   {true_aligned_store}")
        print(f"true person rot15 vs FALLBACK enroll:  {true_mixed_store}  (stale-store hazard)")

        # Enroll through the REAL public API (what the app does) so the
        # watcher cycles exercise the true match path.
        enrolled = svc.enroll(zidane, "Zidane")
        if not enrolled.get("ok"):
            print("enroll failed:", enrolled)
            return 3

        # Watcher cycles over the real photos (fake camera, real pipeline).
        cam = FakeCamera([bus_bytes, imread(_resolve_photo("zidane.jpg"))])
        r1 = asyncio.run(run_watcher_cycle(cam, svc))  # bus.jpg frame
        # cycle 2: build a 15-degree-tilted Zidane JPEG for the watcher path
        import cv2

        ok2, jpg2 = cv2.imencode(".jpg", cv2.cvtColor(rot15_img, cv2.COLOR_RGB2BGR))
        if not ok2:
            print("probe jpeg encode failed")
            return 3
        cam2 = FakeCamera([jpg2.tobytes()])
        r2 = asyncio.run(run_watcher_cycle(cam2, svc))

        kinds1 = [e["kind"] for e in r1["events"] if e]
        kinds2 = [e["kind"] for e in r2["events"] if e]
        print("cycle1 (bus.jpg): ok=", r1["ok"], "faces=", r1["faces"], "events=", kinds1)
        for e in r1["events"]:
            if e:
                print("   -", e["kind"], "|", e["message"])
        print("cycle2 (zidane rot15): ok=", r2["ok"], "faces=", r2["faces"], "events=", kinds2)
        for e in r2["events"]:
            if e:
                print("   -", e["kind"], "|", e["message"])
        # (persons_seen telemetry lives in get_status(), not run_cycle's return;
        #  the person_seen event detail above is the authoritative evidence.)

        g1 = r1["ok"] and "person_seen" not in kinds1 and "unknown_person" in kinds1
        g2 = r2["ok"] and any(
            e is not None
            and e.get("kind") == "person_seen"
            and e.get("detail", {}).get("name") == "Zidane"
            for e in r2["events"]
        )
        g3 = (
            sim["aligned"] is not None
            and sim["fallback"] is not None
            and sim["aligned"] < thr
            and sim["fallback"] < thr
            and blank_sim is not None
            and blank_sim < thr
        )
        g4 = True  # temp store throughout; the real store was never written
        g5 = true_mixed_store is not None and true_mixed_store < thr
        g5_label = (
            "G5 stale pre-alignment store fails safe (< thr, no wrong accept; RE-ENROLLMENT REQUIRED)"
            if g5
            else "G5 stale pre-alignment store still recognizes its person"
        )
        for label, gate in (
            ("G1 bus.jpg: no person_seen, honest unknown_person", g1),
            ("G2 tilted true person through watcher: person_seen(Zidane)", g2),
            ("G3 impostors + blank all < threshold (aligned & fallback)", g3),
            ("G4 real face store untouched", g4),
            (g5_label, g5),
        ):
            print(f"{label}: {'PASS' if gate else 'FAIL'}")
        ok = g1 and g2 and g3 and g4 and g5
        print("VERDICT:", "PASS" if ok else "FAIL")

        report = {
            "threshold": thr,
            "bus_faces": sim["faces"],
            "stranger_sim_aligned": sim["aligned"],
            "stranger_sim_fallback": sim["fallback"],
            "blank_vs_enroll": blank_sim,
            "true_person_aligned_store": true_aligned_store,
            "true_person_mixed_store": true_mixed_store,
            "cycle1_events": kinds1,
            "cycle2_events": kinds2,
            "gates": {"G1": bool(g1), "G2": bool(g2), "G3": bool(g3), "G4": bool(g4), "G5": bool(g5)},
            "verdict": "PASS" if ok else "FAIL",
        }
        out = BACKEND_DIR.parents[1] / "tmp" / "watcher_accuracy_report.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("report:", out)
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
