import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "My Career AI - Realistic AI mock interviews",
  description:
    "Practise real technical interviews with an AI interviewer. Pick a topic or a target company, add your resume and JD, and get detailed feedback.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
