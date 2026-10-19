'use client';

import Link from 'next/link';
import { ArrowRight, Camera, FileCheck2, HardHat, Users, Activity } from 'lucide-react';
import { StatusPill } from './CalmUi';
import type { CentreIntelligence, CentreVerificationMetric, CentreVerificationSnapshot } from '../lib/types';

type Props={centreId:string; verification:CentreVerificationSnapshot|null; action:CentreIntelligence['actions'][number]|null; loading:boolean};
const SURFACE='min-w-0 rounded-2xl border border-[#E6ECF4] bg-white p-4 sm:p-5';
const count=(n:number|null|undefined)=>typeof n==='number'?n.toLocaleString('en-IN'):'—';

function Pair({name,item,href,labels,icon:Icon}:{name:string;item:CentreVerificationMetric|null;
  href:string;labels:[string,string];icon:typeof Users}) {
  const hasFacts=item?.source!=='unavailable'&&item?.reported!=null&&item?.observed!=null;
  return <Link href={href} className={'kw-focus group '+SURFACE+' transition hover:border-[#B6CCE9]'}
    aria-label={name+' verification details'}>
    <div className="flex items-center justify-between gap-2">
      <span className="inline-flex items-center gap-2 text-[12px] font-semibold text-[#253B57]"><Icon size={15} className="text-[#6F8FB2]"/>{name}</span>
      <ArrowRight size={14} className="text-[#91A3B7] group-hover:text-[#2563EB]"/>
    </div>
    <div className="mt-4 grid grid-cols-2 gap-3">
      <div><div className="text-[10px] text-[#8291A6]">{labels[0]}</div>
        <strong className="kw-os-stat mt-1 block text-[26px] font-semibold tabular-nums text-[#22354D]">{count(item?.reported)}</strong></div>
      <div><div className="text-[10px] text-[#8291A6]">{labels[1]}</div>
        <strong className="kw-os-stat mt-1 block text-[26px] font-semibold tabular-nums text-[#22354D]">{count(item?.observed)}</strong></div>
    </div>
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <StatusPill state={item?.status||'unavailable'}/>
      {hasFacts&&<span className="text-[10px] text-[#8291A6]">{item?.simulated?'Simulated · ':''}{item?.source==='case'?'Case evidence':'Analysis record'}</span>}
      {!hasFacts&&<span className="text-[10px] text-[#8291A6]">No trusted comparison</span>}
    </div>
  </Link>;
}

export default function CentreVerificationCockpit({centreId,verification,action,loading}:Props){
  const base='/centres/'+encodeURIComponent(centreId);
  const activity=verification?.practical_activity;
  const camera=verification?.camera.status||'unavailable';
  const suspended=camera==='uncertain';
  return <section aria-label="Centre verification cockpit" className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div><h2 className="text-[20px] font-semibold tracking-tight text-[#243A55]">Verification snapshot</h2>
        <p className="mt-0.5 text-[11px] text-[#7C8DA4]">Recorded observations · officer-reviewed decisions</p></div>
      <Link href={base+'/evidence'} className="kw-focus inline-flex items-center gap-1.5 text-[12px] font-semibold text-[#2563EB]">Evidence <ArrowRight size={14}/></Link>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Pair name="Attendance" href={base+'/attendance'} labels={['Reported','Observed']}
        icon={Users} item={verification?.attendance||null}/>
      <Pair name="Equipment" href={base+'/infrastructure'} labels={['Reported','Visible']}
        icon={HardHat} item={verification?.infrastructure||null}/>
      <Link href={base+'/practical'} className={'kw-focus group '+SURFACE+' transition hover:border-[#B6CCE9]'}>
        <div className="flex items-center justify-between"><span className="inline-flex items-center gap-2 text-[12px] font-semibold text-[#253B57]"><Activity size={15} className="text-[#6F8FB2]"/>Practical activity</span>
          <ArrowRight size={14} className="text-[#91A3B7] group-hover:text-[#2563EB]"/></div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div><div className="text-[10px] text-[#8291A6]">Active work cells</div>
            <strong className="kw-os-stat mt-1 block text-[26px] font-semibold tabular-nums text-[#22354D]">{count(activity?.active_work_cells)}</strong></div>
          <div><div className="text-[10px] text-[#8291A6]">Peak workers</div>
            <strong className="kw-os-stat mt-1 block text-[26px] font-semibold tabular-nums text-[#22354D]">{count(activity?.peak_workers)}</strong></div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusPill state={activity?.status||'unavailable'}/>
          <span className="text-[10px] text-[#8291A6]">{activity?.source==='analysis'?(activity.simulated?'Simulated · Recorded':'Recorded analysis'):'No trusted activity data'}</span>
        </div>
      </Link>
      <Link href={base+'/camera-trust'} className={'kw-focus group '+SURFACE+' transition hover:border-[#B6CCE9]'}>
        <div className="flex items-center justify-between"><span className="inline-flex items-center gap-2 text-[12px] font-semibold text-[#253B57]"><Camera size={15} className="text-[#6F8FB2]"/>Camera & evidence</span>
          <ArrowRight size={14} className="text-[#91A3B7] group-hover:text-[#2563EB]"/></div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div><div className="text-[10px] text-[#8291A6]">Retained items</div>
            <strong className="kw-os-stat mt-1 block text-[26px] font-semibold tabular-nums text-[#22354D]">{verification?verification.evidence.retained_count:'—'}</strong></div>
          <div><div className="text-[10px] text-[#8291A6]">Cases to review</div>
            <strong className="kw-os-stat mt-1 block text-[26px] font-semibold tabular-nums text-[#22354D]">{verification?verification.evidence.cases_requiring_review:'—'}</strong></div>
        </div>
        <div className="mt-3"><StatusPill state={camera}/></div>
      </Link>
    </div>
    {(suspended||action)&&<div className="flex flex-col gap-3 rounded-2xl border border-[#DEE7F2] bg-[#F6F9FD] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 gap-2.5">
        <FileCheck2 size={18} className="mt-0.5 shrink-0 text-[#4779B5]"/>
        <div>
          {suspended ? <h3 className="text-[12px] font-semibold text-[#273E5B]">Camera review required</h3> :
            action ? <Link href={action.href} className="kw-focus text-[12px] font-semibold text-[#273E5B] hover:text-[#2563EB]">{action.title}</Link> :
            <h3 className="text-[12px] font-semibold text-[#273E5B]">Next action</h3>}
          <p className="mt-1 line-clamp-2 text-[11px] text-[#71849D]">{suspended?'Attendance and equipment conclusions paused until camera trust is verified.':action?.reason||'Review the retained evidence.'}</p>
        </div>
      </div>
      <Link href={suspended?base+'/evidence':action?.href||base+'/evidence'}
        className="kw-focus inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-[#2563EB] px-4 py-2.5 text-[12px] font-semibold text-white">
        {suspended?'Inspect evidence':'Review next'}<ArrowRight size={14}/>
      </Link>
    </div>}
    {!verification&&<div role={loading?'status':'alert'} className="rounded-xl border border-[#E4EAF2] bg-white p-4 text-[12px] text-[#667085]">
      {loading?'Loading centre verification…':'Verification data unavailable. No observed values inferred.'}
    </div>}
  </section>;
}
