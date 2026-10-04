'use client';

import { useEffect, useMemo, useState } from 'react';

type Mode='attendance'|'practical'|'infrastructure';

const COPY:Record<Mode,{title:string;steps:string[]}> = {
  attendance:{
    title:'Analysing attendance evidence',
    steps:[
      'Checking camera quality',
      'Detecting people',
      'Building stable anonymous tracks',
      'Comparing with reported attendance',
    ],
  },
  practical:{
    title:'Analysing practical-work evidence',
    steps:[
      'Checking camera quality',
      'Confirming stable workers',
      'Measuring work-cell motion',
      'Joining authorization context',
    ],
  },
  infrastructure:{
    title:'Analysing infrastructure evidence',
    steps:[
      'Reading the manifest',
      'Checking visual evidence',
      'Applying temporal proof',
      'Preparing any review evidence',
    ],
  },
};

export default function AnalysisProgressOverlay({mode}:{mode:Mode}){
  const config=COPY[mode];
  const [index,setIndex]=useState(0);

  useEffect(()=>{
    const timer=window.setInterval(()=>{
      setIndex(current=>(current+1)%config.steps.length);
    },1400);
    return ()=>window.clearInterval(timer);
  },[config.steps.length]);

  const progress=useMemo(
    ()=>Math.round(((index+1)/config.steps.length)*100),
    [index,config.steps.length],
  );

  return <div className="analysisProgressOverlay" role="status" aria-live="polite">
    <div className="analysisProgressCard">
      <div className="analysisProgressOrb"><span></span></div>
      <div className="analysisProgressCopy">
        <small>KaushalWatch pipeline</small>
        <strong>{config.title}</strong>
        <p>{config.steps[index]}</p>
      </div>
      <div className="analysisProgressMeta">{progress}%</div>
      <div className="analysisProgressTrack"><i style={{width:progress+'%'}}></i></div>
      <div className="analysisProgressSteps">
        {config.steps.map((step,stepIndex)=><span
          key={step}
          className={stepIndex<index?'done':stepIndex===index?'active':''}
        ><i>{stepIndex<index?'✓':stepIndex+1}</i>{step}</span>)}
      </div>
    </div>
  </div>;
}
