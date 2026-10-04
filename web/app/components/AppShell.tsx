'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

const primary=[
  ['/', 'Network Overview', 'network'],
  ['/centres', 'Centres', 'centres'],
  ['/escalations', 'Escalations', 'alert'],
  ['/reports', 'Reports', 'report'],
  ['/analytics', 'Analytics', 'analytics'],
] as const;

function Icon({name}:{name:string}){
  const p={width:18,height:18,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.8,strokeLinecap:'round' as const,strokeLinejoin:'round' as const};
  if(name==='network') return <svg {...p}><circle cx="6" cy="6" r="2"/><circle cx="18" cy="7" r="2"/><circle cx="12" cy="18" r="2"/><path d="m7.7 7.1 3.1 8M16.3 8.2l-3 7.7M8 6.2l8 .6"/></svg>;
  if(name==='centres') return <svg {...p}><path d="M4 21h16M6 21V5h12v16M9 9h2M13 9h2M9 13h2M13 13h2"/></svg>;
  if(name==='alert') return <svg {...p}><path d="M12 3 3 20h18L12 3Z"/><path d="M12 9v4M12 17h.01"/></svg>;
  if(name==='report') return <svg {...p}><path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/></svg>;
  if(name==='analytics') return <svg {...p}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>;
  if(name==='attendance') return <svg {...p}><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="m16 11 2 2 4-4"/></svg>;
  if(name==='activity') return <svg {...p}><path d="M3 15h4l2-8 4 12 2-7h6"/></svg>;
  if(name==='infrastructure') return <svg {...p}><path d="M4 20V7l8-4 8 4v13"/><path d="M8 20v-5h8v5"/></svg>;
  if(name==='review') return <svg {...p}><rect x="4" y="4" width="16" height="16" rx="2"/><path d="m8 12 2 2 5-5"/></svg>;
  if(name==='history') return <svg {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>;
  if(name==='settings') return <svg {...p}><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.5-2.4 1a8 8 0 0 0-1.7-1L14.5 3h-5L9 6a8 8 0 0 0-1.7 1L5 6 3 9.5 5 11a7 7 0 0 0 0 2l-2 1.5L5 18l2.4-1a8 8 0 0 0 1.7 1l.4 3h5l.4-3a8 8 0 0 0 1.7-1l2.4 1 2-3.5-2-1.5a7 7 0 0 0 .1-1Z"/></svg>;
  return <svg {...p}><circle cx="12" cy="12" r="8"/></svg>;
}

function active(pathname:string,href:string){
  if(href==='/') return pathname==='/';
  return pathname===href||pathname.startsWith(href+'/');
}

export default function AppShell({children}:{children:ReactNode}){
  const pathname=usePathname();
  const centreMatch=pathname.match(/^\/centres\/([^/]+)/);
  const activeCentre=centreMatch?.[1]||'DEMO-KA-104';
  const selected=[
    [`/centres/${activeCentre}`,'Centre Overview','centres'],
    [`/centres/${activeCentre}/attendance`,'Attendance','attendance'],
    [`/centres/${activeCentre}/practical`,'Practical Work','activity'],
    [`/centres/${activeCentre}/infrastructure`,'Infrastructure','infrastructure'],
    [`/centres/${activeCentre}/review`,'Review Queue','review'],
    [`/centres/${activeCentre}/history`,'History & Audit','history'],
  ] as const;
  return <div className="appFrame">
    <aside className="appSidebar">
      <Link href="/" className="appBrand">
        <span className="appBrandMark">◉</span>
        <span><b>KaushalWatch</b><small>AI for Skilling Integrity</small></span>
      </Link>

      <nav className="appNav">
        {primary.map(([href,label,icon])=><Link key={href} href={href} className={active(pathname,href)?'appNavLink active':'appNavLink'}>
          <Icon name={icon}/><span>{label}</span>
          {label==='Escalations'&&<em>3</em>}
        </Link>)}
      </nav>

      <div className="navDivider"></div>
      <span className="navCaption">Selected Centre</span>
      <nav className="appNav selectedNav">
        {selected.map(([href,label,icon])=><Link key={href} href={href} className={active(pathname,href)?'appNavLink active':'appNavLink'}>
          <Icon name={icon}/><span>{label}</span>
        </Link>)}
      </nav>

      <div className="sidebarBottom">
        <Link href="/settings" className={active(pathname,'/settings')?'appNavLink active':'appNavLink'}><Icon name="settings"/><span>Settings</span></Link>
        <div className="privacyMini"><span>✓</span><div><b>Privacy-first</b><small>No face recognition</small></div></div>
      </div>
    </aside>

    <div className="appMain">
      <header className="globalTopbar">
        <div className="globalSearch">⌕ <span>Search centres, districts, batches…</span></div>
        <div className="topbarActions">
          <span className="topPill">All States⌄</span>
          <span className="topPill">Last 30 days⌄</span>
          <span className="bellDot">♢<i></i></span>
          <span className="avatar">MO</span>
          <div className="officerIdentity"><b>Ministry Officer</b><small>Government of India</small></div>
        </div>
      </header>
      <main className="routeViewport">{children}</main>
    </div>
  </div>;
}
