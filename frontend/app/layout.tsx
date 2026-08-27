import type { Metadata } from "next";
import { DM_Sans, Fraunces, Inter } from "next/font/google";
import "./styles.css";
import "./auth-v2.css";
import "./app-theme.css";
import "./landing.css";
import "./agents.css";
import "./knowledge.css";
import "./inbox.css";
import "./finance.css";
import "./dashboard.css";
import "./team.css";
import "./marketing.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "OperAI — Equipe de IA para PME",
  description:
    "WhatsApp, cobrança e vendas com conhecimento da sua empresa. SaaS com BYOK.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      className={`${dmSans.variable} ${fraunces.variable} ${inter.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
