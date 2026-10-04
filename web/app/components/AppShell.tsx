'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { FormEvent, type ReactNode, useEffect, useRef, useState } from 'react';
import { getCentres } from '../lib/api';

const networkNav=[
  ['/', 'Network Overview', '⌂'],
  ['/centres', 'Centres', '▦'],
  ['/escalations', 'Escalations', '⚠'],
  ['/reports', 'Reports', '▤'],
  ['/analytics', 'Analytics', '◫'],
] as const;

function isActive(pathname:string,href:string){
  if(href==='/') return pathname==='/';
  return pathname===href||pathname.startsWith(href+'/');
}

function routeLabel(pathname:string){
  if(pathname==='/') return 'Network Overview';
  if(pathname==='/centres') return 'Training Centres';
  if(pathname.startsWith('/escalations')) return 'Escalations';
  if(pathname.startsWith('/reports')) return 'Reports';
  if(pathname.startsWith('/analytics')) return 'Analytics';
  if(pathname.startsWith('/settings')) return 'Settings';
  if(pathname.includes('/attendance')) return 'Attendance Verification';
  if(pathname.includes('/practical')) return 'Practical Work Verification';
  if(pathname.includes('/infrastructure')) return 'Infrastructure Verification';
  if(pathname.includes('/review')) return 'Review Queue';
  if(pathname.includes('/history')) return 'History & Audit';
  if(pathname.includes('/outcome')) return 'Review Outcome';
  if(pathname.includes('/analysis')) return 'Centre Analysis';
  if(pathname.startsWith('/centres/')) return 'Centre Overview';
  return 'KaushalWatch';
}

function NavLink({href,label,icon,pathname,badge}:{href:string;label:string;icon:string;pathname:string;badge?:string}){
  return <Link href={href} className={isActive(pathname,href)?'neoNavLink active':'neoNavLink'}>
    <span className="neoNavIcon">{icon}</span>
    <span>{label}</span>
    {badge&&<em>{badge}</em>}
  </Link>;
}

export default function AppShell({children}:{children:ReactNode}){
  const pathname=usePathname();
  const router=useRouter();
  const [search,setSearch]=useState('');
  const [escalationCount,setEscalationCount]=useState(0);
  const viewportRef=useRef<HTMLElement|null>(null);
  const centreMatch=pathname.match(/^\/centres\/([^/]+)/);
  const centreId=centreMatch?.[1]||'DEMO-KA-104';

  useEffect(()=>{
    getCentres().then(payload=>setEscalationCount(payload.centres.filter(c=>c.escalation.level>0).length)).catch(()=>setEscalationCount(0));
  },[pathname]);

  useEffect(()=>{
    const viewport=viewportRef.current;
    if(!viewport) return;
    const lockHorizontalRail=()=>{
      if(viewport.scrollLeft!==0) viewport.scrollLeft=0;
    };
    lockHorizontalRail();
    viewport.addEventListener('scroll',lockHorizontalRail,{passive:true});
    const focusReset=()=>requestAnimationFrame(lockHorizontalRail);
    viewport.addEventListener('focusin',focusReset);
    return ()=>{
      viewport.removeEventListener('scroll',lockHorizontalRail);
      viewport.removeEventListener('focusin',focusReset);
    };
  },[pathname]);

  function submitSearch(event:FormEvent){
    event.preventDefault();
    const q=search.trim();
    router.push(q?'/centres?q='+encodeURIComponent(q):'/centres');
  }

  const centreNav=[
    ['/centres/'+centreId,'Overview','◎'],
    ['/centres/'+centreId+'/attendance','Attendance','◉'],
    ['/centres/'+centreId+'/practical','Practical Work','⌁'],
    ['/centres/'+centreId+'/infrastructure','Infrastructure','▣'],
    ['/centres/'+centreId+'/review','Review Queue','✓'],
    ['/centres/'+centreId+'/history','History & Audit','↺'],
  ] as const;

  return <div className="neoApp">
    <aside className="neoSidebar">
      <Link href="/" className="neoBrand">
        <span className="neoBrandEye"><i></i></span>
        <div><b>KaushalWatch</b><small>AI for Skilling Integrity</small></div>
      </Link>

      <nav className="neoNav">
        {networkNav.map(([href,label,icon])=><NavLink key={href} href={href} label={label} icon={icon} pathname={pathname} badge={label==='Escalations'&&escalationCount>0?String(escalationCount):undefined}/>)}
      </nav>

      <div className="neoNavDivider"></div>
      <div className="neoNavGroupTitle">Selected Centre</div>
      <nav className="neoNav neoCentreNav">
        {centreNav.map(([href,label,icon])=><NavLink key={href} href={href} label={label} icon={icon} pathname={pathname}/>)}
      </nav>

      <div className="neoSidebarFooter">
        <NavLink href="/settings" label="Settings" icon="⚙" pathname={pathname}/>
        <div className="neoPrivacy">
          <span>✓</span>
          <div><b>Privacy-first</b><small>No facial recognition</small></div>
        </div>
      </div>
    </aside>

    <div className="neoMain">
      <header className="neoTopbar">
        <div className="neoBreadcrumb">
          <span>KaushalWatch</span><i>›</i><b>{routeLabel(pathname)}</b>
        </div>
        <form className="neoSearch" onSubmit={submitSearch}>
          <span>⌕</span><input aria-label="Global search" placeholder="Search centres, districts, batches…" value={search} onChange={event=>setSearch(event.target.value)}/><kbd>Enter</kbd>
        </form>
        <div className="neoTopActions">
          <span className="neoLive"><i></i>Monitoring active</span>
          <Link href="/escalations" className="neoIconBtn" aria-label={escalationCount?String(escalationCount)+' active escalations':'No active escalations'}>♢{escalationCount>0&&<i></i>}</Link>
          <div className="neoOfficer">
            <span>MO</span>
            <div><b>Ministry Officer</b><small>Compliance Monitoring</small></div>
          </div>
        </div>
      </header>

      <main ref={viewportRef} className="neoViewport">
        <div className="neoPageGlow"></div>
        {children}
      </main>
    </div>
  </div>;
}
