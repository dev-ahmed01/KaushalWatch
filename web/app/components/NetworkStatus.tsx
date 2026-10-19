'use client';

import { useEffect, useState } from 'react';
import { WifiOff } from 'lucide-react';

/** Connection status is a *device* hint, never proof of API/server health.
 * Does not persist API responses or enqueue sensitive officer review writes. */
export function NetworkStatus(){
  const [offline,setOffline]=useState(false);
  useEffect(()=>{
    const sync=()=>setOffline(!navigator.onLine);
    sync();
    window.addEventListener('online',sync);
    window.addEventListener('offline',sync);
    return ()=>{window.removeEventListener('online',sync);window.removeEventListener('offline',sync);};
  },[]);
  if(!offline)return null;
  return <div role="status" aria-live="polite" data-testid="device-offline"
    className="flex flex-wrap items-center gap-2 border-b border-[#F3DBAC] bg-[#FFF9EA] px-4 py-2.5 text-[11px] font-medium text-[#78551C] sm:px-8">
    <WifiOff size={15} aria-hidden="true"/>
    <span>Device offline — live centre updates and officer decisions need a connection. Saved sample recordings can still play when served locally.</span>
  </div>;
}

export function DataRetry({onRetry,label,disabled=false}:{onRetry:()=>void;label?:string;disabled?:boolean}){
  return <button type="button" onClick={onRetry} disabled={disabled}
    className="kw-focus inline-flex min-h-9 shrink-0 items-center justify-center rounded-xl border border-[#D6E1EF] bg-white px-3 py-2 text-[11px] font-semibold text-[#315D91] hover:bg-[#F5F9FF] disabled:opacity-50">
    {disabled?'Refreshing…':label||'Retry'}
  </button>;
}
