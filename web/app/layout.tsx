import type { Metadata } from "next";
import { Inter, Cormorant_Garamond, Amiri } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-cormorant",
  display: "swap",
});

const amiri = Amiri({
  subsets: ["arabic"],
  weight: ["400", "700"],
  variable: "--font-amiri",
  display: "swap",
});

export const metadata: Metadata = {
  title: "شمس المعارف · Shams al-Ma'arif",
  description:
    "Digital manuscript reader for the 600-page Shams al-Ma'arif grimoire — Arabic, English, Indonesian. OCR text + scanned PDF page view, last-read, bookmarks.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Apply saved theme + line-height BEFORE paint to avoid a flash
            of the default theme on load. Runs before React hydrates. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var k='shams-reader-state-v1';var r=localStorage.getItem(k);if(r){var p=JSON.parse(r);if(p.theme)document.documentElement.dataset.theme=p.theme;if(p.lineHeight)document.documentElement.dataset.line=p.lineHeight;}}catch(e){}})();`,
          }}
        />
      </head>
      <body
        className={`${inter.variable} ${cormorant.variable} ${amiri.variable}`}
      >
        {children}
      </body>
    </html>
  );
}
