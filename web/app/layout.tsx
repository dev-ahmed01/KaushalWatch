import './globals.css';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from './components/AppShell';

export const metadata: Metadata = {
  title: 'KaushalWatch · KaushalAI',
  description: 'AI-powered compliance intelligence for PMKVY training centres',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
