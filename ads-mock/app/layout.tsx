import type { Metadata } from "next"
import { Roboto } from "next/font/google"
import "./globals.css"

const roboto = Roboto({ subsets: ["latin"], weight: ["400", "500", "700"], variable: "--font-roboto-family" })

export const metadata: Metadata = {
  title: "Google Search & Google Ads (Mock) · Uplift demo",
  description: "A mock of Google Search and Google Ads for the Uplift demo. Not affiliated with Google; no real ads run.",
  robots: { index: false, follow: false },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${roboto.variable} antialiased`}>{children}</body>
    </html>
  )
}
