import './globals.css';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from './components/AppShell';

export const metadata: Metadata = {
  title: 'KaushalWatch OS · Training Centre Operations',
  description: 'Training centre attendance, infrastructure and evidence operations',
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
