import './styles.css';
import type { ReactNode } from 'react';

export const metadata = {
  title: 'KaushalWatch Command Centre',
  description: 'Trusted visual compliance prototype for skill training centres'
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
