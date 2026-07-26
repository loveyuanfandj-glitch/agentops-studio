import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AgentOps Studio — Auditable control for tool-using AI agents",
  description:
    "Multi-step orchestration, traces, tenant usage, cost, and guardrails for production-minded AI agents.",
  openGraph: {
    title: "AgentOps Studio",
    description: "Auditable orchestration for tool-using AI agents.",
    images: [
      {
        url: "/portfolio-overview.jpg",
        width: 1512,
        height: 1248,
        alt: "AgentOps Studio synthetic operations dashboard",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AgentOps Studio",
    description: "Auditable orchestration for tool-using AI agents.",
    images: ["/portfolio-overview.jpg"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body>
    </html>
  );
}
