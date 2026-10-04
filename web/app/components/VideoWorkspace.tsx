'use client';

import { ChangeEvent, useRef, type ReactNode } from 'react';
import { EmptyMedia } from './Ui';

export default function VideoWorkspace({
  preview,
  inputName,
  onFile,
  label='Camera / recorded video',
  badge,
  overlay,
}:{
  preview:string;
  inputName:string;
  onFile:(event:ChangeEvent<HTMLInputElement>)=>void;
  label?:string;
  badge?:string;
  overlay?:ReactNode;
}){
  const ref=useRef<HTMLInputElement>(null);
  return <div className="videoWorkspace">
    <div className="videoToolbar">
      <span>▣ {label}</span>
      {badge&&<b>{badge}</b>}
    </div>
    {preview
      ? <div className="videoStage">
          <video src={preview} controls muted playsInline className="analysisVideo"/>
          {overlay&&<div className="videoOverlayLayer" aria-hidden="true">{overlay}</div>}
        </div>
      : <EmptyMedia onUpload={()=>ref.current?.click()}/>
    }
    <input ref={ref} className="hiddenFileInput" type="file" name={inputName} accept="video/*,.mp4,.avi,.mov,.mkv" onChange={onFile}/>
    {preview&&<div className="videoReplace"><button type="button" onClick={()=>ref.current?.click()}>Replace recording</button><span>Local preview · raw video is not uploaded until analysis starts</span></div>}
  </div>;
}
