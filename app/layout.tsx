import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AgentOps Studio — Production control for tool-using AI agents",
  description:
    "Multi-step orchestration, traces, tenant usage, cost, and guardrails for production AI agents.",
  openGraph: {
    title: "AgentOps Studio",
    description: "Production control for tool-using AI agents.",
    images: [
      {
        url: "/og.png",
        width: 1729,
        height: 910,
        alt: "AgentOps Studio operations dashboard",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AgentOps Studio",
    description: "Production control for tool-using AI agents.",
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body>
    </html>
  );
}
