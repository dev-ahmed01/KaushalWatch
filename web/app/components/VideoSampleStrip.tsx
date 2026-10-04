'use client';

import { useEffect, useState } from 'react';

type Frame={src:string;time:number};

export default function VideoSampleStrip({file,count=5}:{file:File|null;count?:number}){
  const [frames,setFrames]=useState<Frame[]>([]);

  useEffect(()=>{
    if(!file){setFrames([]);return;}
    let cancelled=false;
    const url=URL.createObjectURL(file);
    const video=document.createElement('video');
    video.preload='auto';
    video.muted=true;
    video.src=url;

    async function capture(){
      await new Promise<void>((resolve,reject)=>{
        video.onloadedmetadata=()=>resolve();
        video.onerror=()=>reject(new Error('Could not read video metadata'));
      });
      const duration=Number.isFinite(video.duration)&&video.duration>0?video.duration:1;
      const times=Array.from({length:count},(_,index)=>Math.min(duration*.96,duration*((index+1)/(count+1))));
      const output:Frame[]=[];

      for(const time of times){
        if(cancelled) break;
        await new Promise<void>((resolve,reject)=>{
          video.onseeked=()=>resolve();
          video.onerror=()=>reject(new Error('Could not seek video'));
          video.currentTime=time;
        });
        const canvas=document.createElement('canvas');
        const width=240;
        const height=Math.max(120,Math.round(width*((video.videoHeight||9)/(video.videoWidth||16))));
        canvas.width=width;
        canvas.height=height;
        const context=canvas.getContext('2d');
        if(context){
          context.drawImage(video,0,0,width,height);
          output.push({src:canvas.toDataURL('image/jpeg',.72),time});
        }
      }
      if(!cancelled) setFrames(output);
    }

    capture().catch(()=>{if(!cancelled)setFrames([]);});
    return ()=>{cancelled=true;URL.revokeObjectURL(url);video.removeAttribute('src');video.load();};
  },[file,count]);

  return <div className="keyFrameStrip">
    <div className="stripHead"><b>Video Sample Frames</b><span>{frames.length?String(frames.length)+' samples from the uploaded clip':'Generated locally after upload'}</span></div>
    {frames.length
      ? <div className="frameThumbGrid">{frames.map((frame,index)=><figure key={index}><img src={frame.src} alt={'Video sample '+String(index+1)}/><figcaption>{formatTime(frame.time)}</figcaption></figure>)}</div>
      : <div className="framePlaceholders">{Array.from({length:count},(_,i)=><span key={i}>—</span>)}</div>
    }
    <small className="sampleFrameNote">These are navigation samples from the uploaded recording, not AI evidence or identity crops.</small>
  </div>;
}

function formatTime(seconds:number){
  const whole=Math.max(0,Math.floor(seconds));
  const minutes=Math.floor(whole/60);
  const remainder=whole%60;
  return String(minutes)+':'+String(remainder).padStart(2,'0');
}
