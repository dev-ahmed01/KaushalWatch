import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,symlink,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {localTransportReportAllowed,parseOfflineReport,loadPrivateOfflineReport} from './offline-report.ts';

const example={
 schema:'KW_OFFLINE_TRANSPORT_DRILL_V1',
 status:'measured_loopback_fixture_not_field_qualified',
 fixture:true,network_cut_verified:true,queue_survived_restart:true,
 lost_ack_idempotent_reack:true,queued_before:2,delivered:2,remaining:0,
 attempts:3,failed_attempts:2,duplicate_ack_count:2,server_event_rows:2,
 observed_request_body_bytes_final:321,observed_response_body_bytes_final:108,
 observed_request_body_bytes_all_received:642,
 last_success_utc:'2026-10-19T23:30:00+00:00',raw_video_uploaded:false,
 measurement_boundary:'Actually observed loopback bodies; no TLS/IP overhead.',
};
const headers=(host='localhost:3000')=>new Headers({'host':host,'origin':'http://'+host});

test('real observed-body drill can render only under local explicit opt-in',()=>{
 const e={KAUSHALWATCH_ENV:'development',KAUSHALWATCH_LOCAL_OFFLINE_REPORT:'true'};
 assert.equal(localTransportReportAllowed(e,headers()),true);
 assert.equal(localTransportReportAllowed(e,headers('evil.example')),false);
 assert.equal(localTransportReportAllowed({...e,KAUSHALWATCH_WEB_AUTH_MODE:'protected'},headers()),false);
 assert.equal(localTransportReportAllowed({...e,KAUSHALWATCH_ENV:'staging'},headers()),false);
 assert.equal(localTransportReportAllowed({...e,NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY:'true'},headers()),false);
 assert.equal(localTransportReportAllowed({...e,KAUSHALWATCH_STAGING_ACCEPTANCE_STRICT:'true'},headers()),false);
 assert.equal(localTransportReportAllowed({...e,KAUSHALWATCH_LOCAL_OFFLINE_REPORT:'false'},headers()),false);
 assert.equal(localTransportReportAllowed(e,new Headers({'host':'localhost:3000','origin':'http://other.test'})),false);
 assert.equal(localTransportReportAllowed(e,new Headers({'host':'localhost:3000','x-forwarded-host':'evil.test'})),false);
 assert.equal(localTransportReportAllowed(e,new Headers({'host':'localhost:3000','sec-fetch-site':'cross-site'})),false);
});

test('strict measurable fixtures refuse invented bytes, failed reconnect, implied real approval',()=>{
 assert.equal(parseOfflineReport({...example}).delivered,2);
 for(const change of [
  {raw_video_uploaded:true},{fixture:false},{network_cut_verified:false},
  {status:'production_verified'},{delivered:3},{duplicate_ack_count:0},
  {observed_request_body_bytes_final:0},{observed_request_body_bytes_final:-1},
  {observed_request_body_bytes_all_received:100},{last_success_utc:'invalid'},
 ])assert.throws(()=>parseOfflineReport({...example,...change}));
});

test('local file may be read outside public app only and symlink rejected',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'kw-edge-measured-'));
 const file=path.join(dir,'offline-sync.json');
 const link=path.join(dir,'link.json');
 try{
  await writeFile(file,JSON.stringify(example));
  assert.equal((await loadPrivateOfflineReport(file)).observed_request_body_bytes_final,321);
  await symlink(file,link);
  await assert.rejects(()=>loadPrivateOfflineReport(link));
  await writeFile(file,JSON.stringify({...example,delivered:10}));
  await assert.rejects(()=>loadPrivateOfflineReport(file));
 }finally{await rm(dir,{recursive:true,force:true});}
});
