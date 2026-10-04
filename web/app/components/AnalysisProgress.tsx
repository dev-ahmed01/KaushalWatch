'use client';

import { useEffect, useState } from 'react';

const LABELS:Record<string,string[]>={
  attendance:['Reading video','Checking camera trust','Detecting people','Stabilising occupancy','Comparing reported count','Preparing result'],
  practical:['Reading video','Checking camera trust','Tracking workers','Measuring work-cell motion','Joining authorization','Preparing result'],
  infrastructure:['Reading video','Loading manifest','Comparing visible assets','Checking persistence','Preparing evidence','Preparing result'],
};

export default function AnalysisProgress({busy,type}:{busy:boolean;type:'attendance'|'practical'|'infrastructure'}){
  const [index,setIndex]=useState(0);
  useEffect(()=>{
    if(!busy){setIndex(0);return;}
    const timer=window.setInterval(()=>{
      setIndex(current=>Math.min(current+1,(LABELS[type]?.length||1)-1));
    },1400);
    return ()=>window.clearInterval(timer);
  },[busy,type]);

  if(!busy) return null;
  const labels=LABELS[type]||[];
  const progress=Math.round(((index+1)/labels.length)*100);

  return <div className="analysisOverlay" role="status" aria-live="polite">
    <div className="analysisOverlayCard">
      <div className="analysisPulse">✦</div>
      <span className="sectionKicker">ANALYSIS IN PROGRESS</span>
      <h3>{labels[index]}</h3>
      <p>KaushalWatch is processing this clip locally. Final status appears only after the full verification policy completes.</p>
      <div className="analysisProgressBar"><i style={{width:`${progress}%`}}></i></div>
      <div className="analysisPhaseList">
        {labels.map((label,i)=><div key={label} className={i<index?'done':i===index?'active':''}>
          <span>{i<index?'✓':i+1}</span><b>{label}</b>
        </div>)}
      </div>
      <small>Do not close this page while the uploaded clip is being analysed.</small>
    </div>
  </div>;
}
