# My Career AI - web

Next.js app for the candidate experience. See the root README for setup.

- `src/app` - pages: landing, login, dashboard, new interview, loop, interview room, report
- `src/components/interview` - `Lobby` (device and integrity checks), `LiveRoom` (LiveKit voice
  session and proctoring), `CodeEditor` (Monaco, shared with the interviewer)
- `src/lib/proctoring` - media helpers, on-device face checks (MediaPipe), live `Proctor`
- `public/models/blaze_face_short_range.tflite` - MediaPipe face detector model (served locally)
