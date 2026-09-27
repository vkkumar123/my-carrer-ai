import { LinkButton } from "@/components/ui";
import { APP_NAME } from "@/lib/config";

const steps = [
  {
    title: "Pick your target",
    body: "Practise one topic (Spark, SQL, React...) or a full loop for a company and role. Add your resume and paste the JD.",
  },
  {
    title: "Interview by voice",
    body: "An AI interviewer asks questions out loud, follows up on your answers and keeps time, just like a real panel.",
  },
  {
    title: "Real interview conditions",
    body: "Camera on, entire screen shared, fullscreen. The interviewer notices tab switches and pauses if your screen share drops.",
  },
  {
    title: "Get a real debrief",
    body: "Scores per skill with quotes from your answers, what a strong answer looks like, and a study plan.",
  },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-16">
      <p className="text-sm font-medium text-indigo-600">{APP_NAME}</p>
      <h1 className="mt-3 max-w-2xl text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
        Rehearse the real interview before the real interview.
      </h1>
      <p className="mt-5 max-w-2xl text-lg text-slate-600">
        Voice mock interviews tailored to your resume, the job description and the company you&apos;re
        targeting, with honest feedback after every round.
      </p>
      <div className="mt-8 flex gap-3">
        <LinkButton href="/login">Start practising</LinkButton>
        <LinkButton href="/dashboard" variant="secondary">
          My interviews
        </LinkButton>
      </div>
      <div className="mt-16 grid gap-4 sm:grid-cols-2">
        {steps.map((s, i) => (
          <div key={s.title} className="rounded-2xl bg-white p-6 ring-1 ring-slate-200">
            <p className="text-sm font-semibold text-indigo-600">Step {i + 1}</p>
            <h2 className="mt-1 font-semibold text-slate-900">{s.title}</h2>
            <p className="mt-2 text-sm text-slate-600">{s.body}</p>
          </div>
        ))}
      </div>
      <p className="mt-12 text-xs text-slate-500">
        Works on a laptop or desktop with Chrome or Edge. Company loops follow commonly reported
        interview patterns and are not affiliated with any company.
      </p>
    </main>
  );
}
