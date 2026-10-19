"""Produce three offline recorded samples for the Camera Trust showcase.

These are procedurally rendered sample scenarios, not live CCTV or field
validation footage. Must never be used as evidence of detector accuracy.
"""
from pathlib import Path
import math
import hashlib
import json
import subprocess
import tempfile
import cv2
import numpy as np

FPS=12
LENGTH=20
W,H=576,324
SCENES=[
 ("training-bay","CAM 01 / TRAINING BAY","focus",8,13),
 ("workshop-floor","CAM 02 / WORKSHOP","coverage",9,15),
 ("east-corridor","CAM 03 / CORRIDOR","alignment",7,13),
]

def rect(a,x,y,w,h,col):
    cv2.rectangle(a,(x,y),(x+w,y+h),col,-1)

def label(a,s,x,y):
    cv2.putText(a,s,(x,y),cv2.FONT_HERSHEY_SIMPLEX,.41,(226,231,232),1,cv2.LINE_AA)

def human(a,x,y,color):
    x,y=int(x),int(y)
    cv2.ellipse(a,(x,y+26),(12,4),0,0,360,(46,61,71),-1)
    cv2.line(a,(x-4,y+7),(x-7,y+23),(45,51,60),3)
    cv2.line(a,(x+4,y+7),(x+7,y+23),(45,51,60),3)
    rect(a,x-8,y-7,16,21,color)
    cv2.circle(a,(x,y-14),7,(156,183,187),-1)
    rect(a,x-3,y,6,11,(183,215,227))

def frame_for(scene_index,frame_index):
    t=frame_index/FPS
    a=np.full((H,W,3),(68,81,88),dtype=np.uint8)
    rect(a,0,0,W,80,(45,58,66))
    rect(a,0,80,W,H-80,(91,107,114))
    for x in range(0,W,88):
        cv2.line(a,(x,80),(int(W/2+(x-W/2)*1.6),H),(75,88,96),1)
    for y in [138,211,288]:
        cv2.line(a,(0,y),(W,y),(77,94,102),1)
    for x in range(30,W,136):
        rect(a,x,18,81,44,(101,136,151))
        rect(a,x+10,23,60,34,(145,169,179))
    if scene_index==0:
        for x,y in [(40,151),(220,151),(400,151),(130,250),(330,252)]:
            rect(a,x,y,120,27,(58,89,99))
            rect(a,x+18,y-10,28,16,(40,54,65))
        human(a,82+math.sin(t*.75)*48,205,(58,155,209))
        human(a,269+math.cos(t*.5)*47,230,(93,178,213))
        human(a,475+math.sin(t*.45)*31,240,(65,162,223))
    elif scene_index==1:
        for x,y in [(32,148),(212,148),(394,148)]:
            rect(a,x,y,135,47,(60,93,105))
            rect(a,x+15,y-17,84,15,(113,139,148))
        human(a,104+math.sin(t*.7)*50,230,(53,165,198))
        human(a,301+math.cos(t*.6)*45,253,(76,164,222))
        human(a,492+math.sin(t*.35)*27,216,(58,177,192))
    else:
        rect(a,57,94,465,193,(76,94,106))
        cv2.line(a,(173,95),(75,H),(128,162,172),2)
        cv2.line(a,(399,95),(490,H),(128,162,172),2)
        rect(a,245,93,97,110,(41,63,76))
        rect(a,270,133,48,55,(104,139,159))
        human(a,221+math.sin(t*.56)*42,235,(62,155,205))
        human(a,351+math.cos(t*.37)*41,260,(86,178,207))
    a=np.clip(a.astype(np.int16)+int(math.sin(t*2.9)*3),0,255).astype(np.uint8)
    return a

def make(out:Path):
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for index,(name,heading,effect,start,end) in enumerate(SCENES):
            raw=Path(tmp)/(name+".avi")
            w=cv2.VideoWriter(str(raw),cv2.VideoWriter_fourcc(*"MJPG"),FPS,(W,H))
            if not w.isOpened():raise RuntimeError("MJPEG encoder missing")
            for k in range(LENGTH*FPS):
                t=k/FPS
                im=frame_for(index,k)
                if start<=t<end:
                    if effect=="focus":im=cv2.GaussianBlur(im,(27,27),8)
                    elif effect=="coverage":
                        cv2.ellipse(im,(131,133),(207,188),20,0,360,(21,27,34),-1,cv2.LINE_AA)
                    else:
                        im=cv2.warpAffine(im,np.float32([[1,0,54],[0,1,-18]]),(W,H),
                            borderMode=cv2.BORDER_CONSTANT,borderValue=(18,25,32))
                rect(im,0,0,W,26,(27,40,49))
                label(im,heading,12,17)
                label(im,f"RECORDING    00:{int(t):02d}",W-164,17)
                w.write(im)
            w.release()
            dst=out/(name+".mp4")
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(raw),
                "-an","-c:v","libx264","-preset","veryfast","-crf","29",
                "-pix_fmt","yuv420p","-movflags","+faststart",str(dst)],check=True)
            assert dst.stat().st_size>10000
            print(name, dst.stat().st_size)
    receipt={
      "schema":"KW_SUBMISSION_SAMPLE_MEDIA_V1",
      "provenance":"PROCEDURALLY_GENERATED_RECORDING_NOT_REAL_CCTV",
      "clips":{stem:{"sha256":hashlib.sha256((out/(stem+".mp4")).read_bytes()).hexdigest()}
               for stem,_,_,_,_ in SCENES}
    }
    (out/"manifest.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",
                                      encoding="utf-8")

if __name__=="__main__":
    make(Path("web/public/camera-trust"))
