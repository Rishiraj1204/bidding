import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "BIDVERIFY — AI-Powered Bid Compliance Verification Platform",
  description: "Automated, secure, and auditable procurement compliance platform for GeM (SIH PS 26100)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className={`${inter.className} min-h-full bg-slate-900 text-slate-100 antialiased`}>
        {children}
      </body>
    </html>
  );
}
