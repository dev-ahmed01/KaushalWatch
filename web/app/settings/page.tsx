'use client';

import { useEffect, useState } from 'react';
import AssistantPanel from '../components/AssistantPanel';
import { getCentres, getSettings, saveSettings } from '../lib/api';
import type { Centre } from '../lib/types';
import { PageHeader, Status } from '../components/Ui';

export default function SettingsPage(){
  const [centres,setCentres]=useState<Centre[]>([]);
  const [centreId,setCentreId]=useState('DEMO-KA-104');
  const [settings,setSettings]=useState<any>(null);
  const [saved,setSaved]=useState(false);

  useEffect(()=>{getCentres().then(r=>setCentres(r.centres)).catch(()=>{});},[]);
  useEffect(()=>{getSettings(centreId).then(setSettings).catch(()=>{});},[centreId]);

  async function save(){
    if(!settings) return;
    const next=await saveSettings(centreId,settings);
    setSettings(next);
    setSaved(true);
    setTimeout(()=>setSaved(false),1800);
  }

  if(!settings) return <div className="pageScene fadeIn"><PageHeader eyebrow="Configuration" title="Settings" subtitle="Loading centre settings…"/></div>;

  return <div className="pageScene fadeIn">
    <PageHeader eyebrow="Configuration" title="Settings & Configuration" subtitle="Control automatic analysis, low-bandwidth behaviour, escalation rules and privacy defaults."
      actions={<><select className="headerSelect" value={centreId} onChange={e=>setCentreId(e.target.value)}>{centres.map(c=><option key={c.centre_id} value={c.centre_id}>{c.name}</option>)}</select><button className="primaryBtn" onClick={save}>{saved?'Saved ✓':'Save Changes'}</button></>}/>

    <div className="settingsLayout">
      <div className="settingsMain">
        <section className="panel settingsCard">
          <div className="panelHead"><div><span className="sectionKicker">Analysis schedule</span><h2>Automatic monitoring policy</h2></div><Status tone={settings.automatic_analysis?'good':'neutral'}>{settings.automatic_analysis?'Configured':'Manual'}</Status></div>
          <div className="settingRows">
            <label className="switchRow"><div><b>Automatic analysis policy</b><small>Allow a connected live/edge camera source to trigger checks in the configured windows. Without a connected source, no analysis is falsely recorded.</small></div><input type="checkbox" checked={Boolean(settings.automatic_analysis)} onChange={e=>setSettings({...settings,automatic_analysis:e.target.checked})}/></label>
            <label><span>Frequency</span><select value={settings.frequency} onChange={e=>setSettings({...settings,frequency:e.target.value})}><option value="every_training_day">Every training day</option><option value="daily">Daily</option><option value="manual">Manual only</option></select></label>
            <label><span>Monitoring windows</span><input value={(settings.monitoring_windows||[]).join(', ')} onChange={e=>setSettings({...settings,monitoring_windows:e.target.value.split(',').map((v:string)=>v.trim()).filter(Boolean)})}/></label>
          </div>
          <div className="bandwidthNote">Scheduling policy is stored centrally. Unattended execution requires the centre's live/edge capture agent to be connected to a camera source.</div>
        </section>

        <section className="panel settingsCard">
          <div className="panelHead"><div><span className="sectionKicker">Escalation policy</span><h2>When issues move upward</h2></div></div>
          <div className="settingRows">
            <label><span>Repeated attendance discrepancies</span><div className="inlineSetting"><input type="number" min="1" value={settings.escalation_rules?.repeated_attendance_days??3} onChange={e=>setSettings({...settings,escalation_rules:{...settings.escalation_rules,repeated_attendance_days:Number(e.target.value)}})}/><small>training days → regional attention</small></div></label>
            <label><span>Unresolved case age</span><div className="inlineSetting"><input type="number" min="1" value={settings.escalation_rules?.unresolved_case_days??3} onChange={e=>setSettings({...settings,escalation_rules:{...settings.escalation_rules,unresolved_case_days:Number(e.target.value)}})}/><small>days → escalation</small></div></label>
            <label className="switchRow"><div><b>Multi-signal escalation</b><small>Increase priority when attendance, infrastructure, camera or evidence-integrity signals combine.</small></div><input type="checkbox" checked={Boolean(settings.escalation_rules?.multi_signal_escalation)} onChange={e=>setSettings({...settings,escalation_rules:{...settings.escalation_rules,multi_signal_escalation:e.target.checked}})}/></label>
            <label className="switchRow"><div><b>Duplicate-evidence escalation</b><small>Treat repeated possible duplicate evidence as an independent integrity signal.</small></div><input type="checkbox" checked={Boolean(settings.escalation_rules?.duplicate_evidence_escalation)} onChange={e=>setSettings({...settings,escalation_rules:{...settings.escalation_rules,duplicate_evidence_escalation:e.target.checked}})}/></label>
          </div>
        </section>

        <section className="panel settingsCard">
          <div className="panelHead"><div><span className="sectionKicker">Connectivity</span><h2>Low-bandwidth deployment</h2></div><Status tone="info">{String(settings.connectivity_mode).replace('_',' ')}</Status></div>
          <div className="connectivityChoices">
            <button className={settings.connectivity_mode==='normal'?'active':''} onClick={()=>setSettings({...settings,connectivity_mode:'normal'})}><b>Normal</b><small>Standard evidence sync</small></button>
            <button className={settings.connectivity_mode==='low_bandwidth'?'active':''} onClick={()=>setSettings({...settings,connectivity_mode:'low_bandwidth'})}><b>Low bandwidth</b><small>Edge summaries + exception evidence only</small></button>
          </div>
          <div className="bandwidthNote">Raw continuous video is not required for central monitoring. Edge analysis can buffer locally and sync summaries plus exception evidence when connectivity is available.</div>
        </section>
      </div>

      <div className="settingsSide">
        <section className="panel trustCard">
          <span className="sectionKicker">Privacy & safety</span><h2>Locked product rules</h2>
          <div className="trustRule">✓ No face recognition for attendance</div>
          <div className="trustRule">✓ Detector failure never becomes a real zero count</div>
          <div className="trustRule">✓ Camera-trust failures suspend conclusions</div>
          <div className="trustRule">✓ Final compliance decision requires human review</div>
          <div className="trustRule">✓ Authorization is external context, not inferred from pixels</div>
        </section>
        <AssistantPanel centreId={centreId}/>
      </div>
    </div>
  </div>;
}
