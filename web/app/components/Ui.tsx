'use client';

import type { ReactNode } from 'react';

export function PageHeader({eyebrow,title,subtitle,actions}:{eyebrow?:string;title:string;subtitle?:string;actions?:ReactNode}){
  return <header className="pageHeader">
    <div className="pageHeaderLead">
      {eyebrow&&<span className="pageEyebrow">{eyebrow}</span>}
      <h1>{title}</h1>
      {subtitle&&<p>{subtitle}</p>}
    </div>
    {actions&&<div className="pageHeaderActions">{actions}</div>}
  </header>;
}

export function Status({tone='neutral',children}:{tone?:'good'|'warn'|'danger'|'info'|'neutral';children:ReactNode}){
  return <span className={'statusChip '+tone}><i></i>{children}</span>;
}

export function Metric({label,value,note,tone='default',icon}:{label:string;value:string|number;note?:string;tone?:'default'|'good'|'warn'|'danger';icon?:string}){
  return <article className={'metricCard '+tone}>
    <span className="metricIcon">{icon||'•'}</span>
    <div><small>{label}</small><strong>{value}</strong>{note&&<p>{note}</p>}</div>
  </article>;
}

export function EmptyMedia({title='No video available',text='No live feed or recorded clip is connected for this camera.',onUpload,onRetry}:{title?:string;text?:string;onUpload?:()=>void;onRetry?:()=>void}){
  return <div className="emptyMedia">
    <div className="emptyCamera"><span></span></div>
    <div className="emptyMediaCopy"><h3>{title}</h3><p>{text}</p></div>
    <div className="emptyActions">
      {onRetry&&<button type="button" className="secondaryBtn" onClick={onRetry}>Retry connection</button>}
      {onUpload&&<button type="button" className="primaryBtn" onClick={onUpload}>Upload recorded video</button>}
    </div>
    <div className="emptyMediaHint"><span>✓</span> Analysis can still run on an uploaded recording.</div>
  </div>;
}

export function Skeleton({lines=4}:{lines?:number}){
  return <div className="skeletonBlock">{Array.from({length:lines}).map((_,i)=><span key={i}></span>)}</div>;
}

export function OutcomeCard({tone,title,text}:{tone:'good'|'warn'|'danger'|'blocked';title:string;text:string}){
  return <div className={'outcomeCard '+tone}>
    <span className="outcomeIcon">{tone==='good'?'✓':tone==='blocked'?'×':'!'}</span>
    <div><strong>{title}</strong><p>{text}</p></div>
  </div>;
}

export function AnimatedNumber({value}:{value:number}){
  return <span className="countPop">{value}</span>;
}
