import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "KrokBot C2 | Agent Control Center",
  description: "Autonomous Fleet Command & Control Center for KrokBot Multi-Agent Systems",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} dark`}>
      <body className="min-h-screen bg-[#070908] text-[#c0d0c8] antialiased selection:bg-[#00ff66]/30 selection:text-[#00ff66]">
        {children}
      </body>
    </html>
  );
}
