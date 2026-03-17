import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TradingAgents Report Viewer",
  description: "Browse and read analysis reports from TradingAgents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
