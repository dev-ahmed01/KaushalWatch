import './globals.css';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from './components/AppShell';
import { Bricolage_Grotesque, Poppins } from 'next/font/google';

// The fonts are fetched at build time and served from _next/static.
// Presentation browsers make no requests to Google Fonts.
const headings = Bricolage_Grotesque({
  subsets: ['latin'],
  weight: ['500','600','700'],
  display: 'swap',
  variable: '--kw-loaded-heading',
});
const bodyFont = Poppins({
  subsets: ['latin'],
  weight: ['400','500','600'],
  display: 'swap',
  variable: '--kw-loaded-body',
});

export const metadata: Metadata = {
  title: 'KaushalWatch OS · Training Centre Operations',
  description: 'Training centre attendance, infrastructure and evidence operations',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={headings.variable+' '+bodyFont.variable}>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
