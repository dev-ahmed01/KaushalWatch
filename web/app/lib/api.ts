import type { AssistantReply, Centre } from './types';

export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function parse<T>(response:Response):Promise<T>{
  const payload=await response.json().catch(()=>null);
  if(!response.ok) throw new Error(payload?.detail||'KaushalWatch API request failed');
  return payload as T;
}

export async function getCentres(){
  return parse<{centres:Centre[];total:number}>(await fetch(`${API}/api/centres`,{cache:'no-store'}));
}

export async function getCentre(centreId:string){
  return parse<Centre>(await fetch(`${API}/api/centres/${encodeURIComponent(centreId)}`,{cache:'no-store'}));
}

export async function getDashboard(centreId?:string,batchId?:string){
  const params=new URLSearchParams();
  if(centreId) params.set('centre_id',centreId);
  if(batchId) params.set('batch_id',batchId);
  return parse<any>(await fetch(`${API}/api/dashboard?${params.toString()}`,{cache:'no-store'}));
}

export async function getHistory(centreId:string,limit=100){
  return parse<{rows:any[]}>(await fetch(`${API}/api/analysis-history?centre_id=${encodeURIComponent(centreId)}&limit=${limit}`,{cache:'no-store'}));
}

export async function askAssistant(centreId:string,question:string,period='7d'){
  return parse<AssistantReply>(await fetch(`${API}/api/assistant/query`,{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({centre_id:centreId,question,period}),
  }));
}

export async function getSettings(centreId:string){
  return parse<any>(await fetch(`${API}/api/centres/${encodeURIComponent(centreId)}/settings`,{cache:'no-store'}));
}

export async function saveSettings(centreId:string,payload:Record<string,unknown>){
  return parse<any>(await fetch(`${API}/api/centres/${encodeURIComponent(centreId)}/settings`,{
    method:'PUT',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload),
  }));
}

export function reportUrl(centreId:string,period='7d'){
  return `${API}/api/centres/${encodeURIComponent(centreId)}/report?period=${encodeURIComponent(period)}`;
}
