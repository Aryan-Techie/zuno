import type { Metadata } from "next";
import "./globals.css";
import "./features.css";
import "./modes.css";

export const metadata: Metadata = {
  title: "Zuno Console",
};

// Applies the saved theme before first paint so a dark-mode operator never
// sees a white flash. Inline so it runs before any stylesheet resolves. The
// console also gets its saved mode here, so a perfume-mode operator does not
// see the Apple theme flash in before React mounts.
const themeScript = `(function(){try{var r=document.documentElement;var s=localStorage.getItem('zuno-theme');var d=s?s==='dark':matchMedia('(prefers-color-scheme: dark)').matches;r.dataset.theme=d?'dark':'light';if(location.pathname==='/'){var m=localStorage.getItem('zuno-mode');if(m==='perfume')r.dataset.mode=m;}}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Instrument+Serif:ital@0;1&family=Bodoni+Moda:ital,opsz,wght@0,6..96,400..700;1,6..96,400..700&display=swap"
        />
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
