"""Cross-image recognition verification for SFace landmark alignment.

Uses the REAL SFace model (no fake sessions) on a deterministic synthetic
"face" whose landmark positions are known exactly. Enrollment happens once
upright; probes are rotated (15deg, 30deg) and scaled (0.7x) variants of the
same face. For every probe we embed twice:

  aligned   - via the 5-point similarity warp (the new path)
  fallback  - via the legacy margin-crop (landmarks withheld)

and report cosine similarity against the corresponding enrollment vector.
Honest limitations, stated up front:
- YuNet is NOT exercised on these frames: it is trained on real faces and
  cannot be trusted on synthetic ones. Landmarks are the known ground truth.
  (When a real camera + face are present, YuNet supplies landmarks in
  production; its row-passthrough is covered by unit tests.)
- A synthetic texture is not a human face, so this measures EMBEDDING
  GEOMETRIC STABILITY (does alignment remove pose variation from the
  embedding), not real-face verification accuracy.

Verdict gates (recognition is the decision that matters):
- G1 recognition: every pose/scale probe's ALIGNED similarity >= threshold.
- G2 stability: every aligned similarity >= 0.95.
- G3 pose advantage: for rotation probes, aligned > fallback (alignment's
  geometric claim lives in pose, not scale — both paths resize to 112x112,
  so uniform scale largely cancels and a ceiling tie is expected there).
- G4 (untestable here): no-false-accept / different-face separation needs a
  REAL face. Measured anyway for honesty: two different synthetic faces
  embed at ~0.9998 similarity — SFace collapses random-textured ovals, so
  synthetic probes cannot falsify the pipeline on identity. The different-
  face number is reported as data, not gated.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dash_backend.vision import recognition as rec  # noqa: E402

THRESHOLD = rec.MATCH_THRESHOLD


def make_face_canvas(size: int, scale: float, seed: int) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """A textured synthetic face with landmark blobs at canonical*scale positions."""
    rng = np.random.default_rng(seed)
    img = np.full((size, size, 3), 40, dtype=np.uint8)
    lm = [(x * scale, y * scale) for x, y in rec._ARCFACE_DST_LANDMARKS]
    xs, ys = np.meshgrid(np.arange(size), np.arange(size))
    cx = sum(p[0] for p in lm) / 5.0
    cy = sum(p[1] for p in lm) / 5.0
    radius = 46.0 * scale
    oval = ((xs - cx) / radius) ** 2 + ((ys - cy) / (radius * 1.25)) ** 2 <= 1.0
    texture = rng.integers(90, 180, size=(size, size, 3), dtype=np.uint8)
    img[oval] = texture[oval]  # textured face oval on dark background
    for i, (x, y) in enumerate(lm):
        xi, yi = int(round(x)), int(round(y))
        shade = 40 + i * 45
        img[max(0, yi - 5) : yi + 5, max(0, xi - 5) : xi + 5] = (shade, shade, shade)
    return img, [(float(x), float(y)) for x, y in lm]


def rotate(canvas: np.ndarray, lm: list[tuple[float, float]], deg: float):
    import cv2

    h, w = canvas.shape[:2]
    mat = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    out = cv2.warpAffine(canvas, mat, (w, h))
    pts = [
        (float(mat[0, 0] * x + mat[0, 1] * y + mat[0, 2]),
         float(mat[1, 0] * x + mat[1, 1] * y + mat[1, 2]))
        for x, y in lm
    ]
    return out, pts


def scale_variant(canvas: np.ndarray, lm: list[tuple[float, float]], factor: float):
    import cv2

    h, w = canvas.shape[:2]
    out = cv2.resize(canvas, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_AREA)
    return out, [(x * factor, y * factor) for x, y in lm]


def main() -> int:
    if not rec.vision_models_dir().exists():
        print("models missing:", rec.vision_models_dir())
        return 2
    svc = rec.FaceRecognitionService()
    if not svc.available:
        print("face service unavailable:", svc.unavailable_reasons())
        return 2

    box = [30, 30, 210, 210]  # margin-crop window for the fallback path
    canvas, lm = make_face_canvas(240, scale=2.0, seed=7)

    t0 = time.perf_counter()
    vec_e_aligned = svc._aligned_embedding(canvas, box, lm)
    vec_e_fallback = svc._aligned_embedding(canvas, box, None)
    load_s = time.perf_counter() - t0
    if vec_e_aligned is None or vec_e_fallback is None:
        print("enrollment embedding failed")
        return 2

    probes: list[tuple[str, np.ndarray, list[tuple[float, float]], str]] = [
        ("same frame (sanity)", canvas, lm, "identity"),
        ("rot 15deg", *rotate(canvas, lm, 15.0), "pose"),
        ("rot 30deg", *rotate(canvas, lm, 30.0), "pose"),
        ("rot 45deg", *rotate(canvas, lm, 45.0), "pose"),
        ("rot 60deg", *rotate(canvas, lm, 60.0), "pose"),
        ("rot 90deg", *rotate(canvas, lm, 90.0), "pose"),
        ("scale 0.7x", *scale_variant(canvas, lm, 0.7), "scale"),
        ("scale 1.3x", *scale_variant(canvas, lm, 1.3), "scale"),
    ]

    # A second, different synthetic face: identity separation probe.
    other, other_lm = make_face_canvas(240, scale=2.0, seed=99)

    rows = []
    for name, frame, pts, kind in probes:
        va = svc._aligned_embedding(frame, box, pts)
        vf = svc._aligned_embedding(frame, box, None)
        rows.append(
            {
                "probe": name,
                "kind": kind,
                "aligned_sim": None if va is None else round(rec._cosine(va, vec_e_aligned), 4),
                "fallback_sim": None if vf is None else round(rec._cosine(vf, vec_e_fallback), 4),
            }
        )
    # Different face embedded through the ALIGNED path (the production path):
    vo_aligned = svc._aligned_embedding(other, box, other_lm)
    other_sim = None if vo_aligned is None else round(rec._cosine(vo_aligned, vec_e_aligned), 4)

    w = max(len(r["probe"]) for r in rows)
    print(f"SFace cross-image stability (threshold {THRESHOLD}) | SFace load {load_s:.1f}s")
    print(f"{'probe':<{w}}   aligned   fallback   aligned-win")
    for r in rows:
        a, f = r["aligned_sim"], r["fallback_sim"]
        win = "-" if (a is None or f is None) else ("yes" if a >= f else "no")
        print(f"{r['probe']:<{w}}   {a!s:>7}   {f!s:>8}   {win:>6}")
    print(f"{'DIFFERENT face (aligned)':<{w}}   {other_sim!s:>7}   {'-':>8}   (must be < {THRESHOLD})")

    g1 = all(r["aligned_sim"] is not None and r["aligned_sim"] >= THRESHOLD for r in rows)
    g2 = all(r["aligned_sim"] is not None and r["aligned_sim"] >= 0.95 for r in rows)
    g3 = all(
        r["aligned_sim"] is not None
        and r["fallback_sim"] is not None
        and r["aligned_sim"] > r["fallback_sim"]
        for r in rows
        if r["kind"] == "pose"
    )
    for label, gate in (
        ("G1 recognition", g1),
        ("G2 stability", g2),
        ("G3 pose advantage", g3),
        ("G4 no false accept", "needs a real face (see report)"),
    ):
        print(f"{label}: {'PASS' if gate is True else ('FAIL' if gate is False else gate)}")
    ok = g1 and g2 and g3
    print("VERDICT:", "PASS" if ok else "FAIL")
    report = {"threshold": THRESHOLD, "rows": rows, "different_face_sim": other_sim, "verdict": "PASS" if ok else "FAIL"}
    out = Path(__file__).resolve().parents[2] / "tmp" / "face_alignment_report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("report:", out)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
