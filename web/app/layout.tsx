import './styles.css';
import type { ReactNode } from 'react';
import AppShell from './components/AppShell';

export const metadata = {
  title: 'KaushalWatch',
  description: 'AI compliance monitoring for distributed skill-training centres'
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en"><body><AppShell>{children}</AppShell></body></html>;
}
