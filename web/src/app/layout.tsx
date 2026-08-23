import type { Metadata, Viewport } from "next";
import "./globals.css";
import RegisterSW from "@/components/RegisterSW";
import DemoBanner from "@/components/DemoBanner";

export const metadata: Metadata = {
  title: "Fasal Kavach — Climate Early-Warning for Farmers",
  description:
    "Climate early-warning and crop advisory for smallholder farmers. " +
    "Rules decide risk; AI communicates it in your language.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Fasal Kavach",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#1B1A15",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="hi">
      <head>
        {/* Fonts load from the CDN rather than next/font because next/font's
            build-time optimisation needs a running Next server, which a
            static export does not have.

            Archivo   — display + UI. Condensed, industrial; the lettering of
                        a painted mandi advisory board.
            IBM Plex Mono — every number in the app. Temperatures, rainfall,
                        days-after-sowing read as instrument output, not prose.
            Noto Sans Devanagari / Bengali — Hindi, Khortha, Bengali. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&family=Noto+Sans+Devanagari:wght@400;500;600;700&family=Noto+Sans+Bengali:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
      </head>
      <body>
        <RegisterSW />
        <DemoBanner />
        {children}
      </body>
    </html>
  );
}
