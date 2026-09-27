/** On-device face checks with MediaPipe. Video never leaves the browser. */

import { FaceDetector, FilesetResolver } from "@mediapipe/tasks-vision";

import { vendorUrl } from "../vendor";


const MODEL_URL = "/models/blaze_face_short_range.tflite";

export interface FaceSample {
  faces: number;
  /** Rough head turn: 0 = facing camera, ~1 = turned fully sideways. Null without a face. */
  yaw: number | null;
}

let detectorPromise: Promise<FaceDetector> | null = null;

export function loadFaceDetector(): Promise<FaceDetector> {
  if (!detectorPromise) {
    detectorPromise = (async () => {
      const vision = await FilesetResolver.forVisionTasks(vendorUrl("mediapipe"));
      return FaceDetector.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.6,
      });
    })();
    detectorPromise.catch(() => {
      detectorPromise = null;
    });
  }
  return detectorPromise;
}

export function sampleFace(detector: FaceDetector, video: HTMLVideoElement): FaceSample | null {
  if (video.readyState < 2 || video.videoWidth === 0) return null;
  const { detections } = detector.detectForVideo(video, performance.now());
  if (detections.length !== 1) return { faces: detections.length, yaw: null };
  // BlazeFace keypoints: 0 right eye, 1 left eye, 2 nose tip, 3 mouth, 4/5 ears.
  const k = detections[0].keypoints;
  if (k.length < 3) return { faces: 1, yaw: null };
  const eyeMid = (k[0].x + k[1].x) / 2;
  const eyeDist = Math.abs(k[1].x - k[0].x) || 1e-3;
  return { faces: 1, yaw: Math.min(1, Math.abs(k[2].x - eyeMid) / eyeDist) };
}

/** Consecutive-sample thresholds that turn noisy per-frame results into events. */
export const FACE_RULES = {
  sampleMs: 1500,
  noFaceSamples: 3, // ~4.5s without a face
  multiFaceSamples: 2,
  lookAwaySamples: 4, // ~6s turned away
  lookAwayYaw: 0.45,
};
