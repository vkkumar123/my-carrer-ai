# My Career AI - Product brief (v1)

Agreed with the founder on 2026-09-27. This is the reference for what we build and what we don't.

## Who it's for

Final-year (4th year) students through IT professionals with up to 15 years of experience,
in India. Any role (SDE, data, frontend, DevOps, ...), targeting any company from tier 3 to
FAANG/MANG.

## Product promise

A mock interview that feels like the real one: a strict, realistic interviewer, real
interview conditions (camera, entire screen shared, proctoring), and an honest report.
No coaching during the interview in v1.

## Offers and pricing (founder's proposal)

| Offer | Price | Contents |
|---|---|---|
| Topic interview | Rs 99 | 3 takes of one topic (e.g. SQL) |
| Company loop | Rs 499 | All technical rounds for a company + role (no HR round) |

Prices include 18% GST, so net revenue is about Rs 84 and Rs 423, minus about 2% payment fees.

## The interviewer (v1 behaviour)

- **Real interviewer mode only.** No teaching or feedback during the round. Feedback comes
  in the report.
- **Coding and SQL questions: approach first.** Ask for the approach and logic first, then
  have the candidate write it, run it, and discuss edge cases and complexity.
- **Help:** when the candidate asks for help or is clearly stuck, guide them with small
  progressive hints the way a real interviewer does. Never give the answer.
- **Languages:** understands and replies in English, Hindi and Hinglish. If the candidate
  switches to Hindi, the interviewer follows.
- **Voice:** Indian-accent voice. The candidate picks male or female in the lobby.
- **Length:** company rounds last 45-60 minutes. The interviewer may end early (from about
  25-30 minutes) when the candidate clearly can't progress: "I think that's all the questions
  I had", as in real interviews.
- **Integrity:** first violation gets a warning. A repeat gets a final warning that says
  plainly the next one ends the interview. After that, the interviewer ends the round and
  states the reason.

## Workspace

- Problem panel with the question's details; code editor and whiteboard in every round
  (already built).
- **Run code in the browser:** SQL against the question's sample tables (DuckDB in the
  browser) and Python (Pyodide). The interviewer sees the code and the run output. No server
  cost.

## Company realism

The AI researches each company + role on the open web (Reddit, Glassdoor-style write-ups,
LeetCode Discuss, blogs and public LinkedIn posts) and drafts the loop's round structure and
question style from that. Research is cached per company + role for about 30 days and shared
across candidates, so it is paid for once. Sources are summarised, never copied.
Note: most LinkedIn content needs a login and can't be searched automatically; public posts
that search engines index can be.

## Report

Per-round debrief (built), plus:
- score trend over time, per skill
- comparison with other candidates (percentile), shown once enough candidates have taken
  the same topic or company for it to mean something
- recording playback: later phase (storage and recording cost)

## Constraints

- Solo founder; AI + hosting budget Rs 10,000-20,000 per month for the first 3 months.
- First users: the founder's friends, as soon as a deployed version exists.

## Out of scope for v1

Coaching/practice mode, HR rounds, video avatar interviewer, recording playback,
B2B/college dashboards.

## Decisions (2026-09-27)

- **Pricing:** keep Rs 99 / Rs 499 for now and accept running at a loss during the beta;
  revisit with measured cost per interview-minute.
- **Voice:** Sarvam AI (Indian-accent male/female voices; Hindi, English, Hinglish).
- **Beta:** free for the founder's friends on staging; Razorpay payments next, before public
  launch.
- **Build order:** beta-ready bundle (voice, run code, approach-first, early end, integrity
  escalation, company web research), then deploy to staging.

## Unit economics (to measure)

Voice interviews cost money per minute (speech-to-text, text-to-speech, the LLM for each
turn, realtime media). Estimates must be measured on staging in the first week; at an assumed
Rs 2-5 per interview-minute:

| Offer | Voice minutes | Estimated cost | Net revenue |
|---|---|---|---|
| Topic, 3 takes x 20 min | 60 | Rs 120-300 | ~Rs 84 |
| Company loop, 4 rounds x 50 min | 200 | Rs 400-1,000 | ~Rs 423 |

Levers: an India-priced voice provider (Sarvam: Indian voices, Hindi/Hinglish), prompt
caching, self-hosted LiveKit, and adjusting what each price includes.
