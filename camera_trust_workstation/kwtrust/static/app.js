(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const escape = x => String(x).replace(/[&<>"']/g, a => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[a]));
  let report = null;
  const comma = num => Number(num).toLocaleString('en-IN');
  const persist = w => w.policies.sharpness_3_consecutive;
  const renderTable = () => {
    const day = $('day').value, signal = $('signal').value, search = $('filter').value.trim().toLowerCase();
    const rows = report.priority_queue.filter(w => (day === 'all' || day === w.day) &&
      (signal === 'all' || (signal === 'positive') === persist(w).window_with_candidate) &&
      (`${w.start_frame} ${w.end_frame} ${w.stratum}`.toLowerCase().includes(search)));
    $('casecount').textContent = `${rows.length} / ${report.number_of_windows} windows`;
    $('table-body').innerHTML = rows.map(w => {
      const video = w.local_video_evidence || {};
      const hasVideo = video.status === 'UNVERIFIED_LOCAL_VIDEO_FEATURES_NOT_GROUND_TRUTH';
      const episodes = persist(w).episodes;
      return `<tr><td>${escape(w.day.toUpperCase())}</td><td>${comma(w.start_frame)} – ${comma(w.end_frame)}</td>
      <td>${escape(w.stratum)}</td><td><span class="pill ${episodes ? 'warn' : 'good'}">${episodes} candidate${episodes===1?'':'s'}</span></td>
      <td>${w.illumination_confounded_samples} / 90 samples</td><td><span class="pill ${hasVideo ? 'good' : ''}">${hasVideo ? 'Numeric features only' : (report.recordings_available_in_workspace ? 'Not sampled (budget)' : 'AVI not mounted')}</span></td></tr>`;
    }).join('') || '<tr><td colspan="6">No cases match this filter.</td></tr>';
  };
  const render = data => {
    report = data;
    $('m-windows').textContent = comma(data.number_of_windows);
    $('m-hours').textContent = `${data.selected_normal_labeled_hours.toFixed(1)} h`;
    $('m-episodes').textContent = comma(Object.values(data.by_day).reduce((n,d) => n + d.policy_candidates.sharpness_3_consecutive.candidate_episode_starts,0));
    $('state').textContent = data.recordings_available_in_workspace ?
      'Prior AVI numerical features available — local recordings need not be mounted now; physical health unverified' :
      'Original AVI files not mounted — video inspection not yet possible';
    const coverage = data.video_feature_coverage || (() => {
      const measured = data.priority_queue.filter(w => w.local_video_evidence?.status === 'UNVERIFIED_LOCAL_VIDEO_FEATURES_NOT_GROUND_TRUTH');
      return {selected_windows: data.number_of_windows, measured_windows: measured.length,
              unmeasured_windows: data.number_of_windows-measured.length,
              sampled_video_frames: measured.reduce((n,w) => n+(w.local_video_evidence.sampled_source_frames||0),0)};
    })();
    $('video-coverage').innerHTML = [
      [coverage.measured_windows + '/' + coverage.selected_windows, 'windows with actual AVI features'],
      [coverage.sampled_video_frames, 'decoded video frames'],
      [coverage.unmeasured_windows, 'selected windows still lacking AVI features']
    ].map(([value,label]) => '<div class="event-group"><strong>'+escape(value)+'</strong><span>'+escape(label)+'</span></div>').join('');
    const rows = Object.entries(data.by_day);
    const max = Math.max(1, ...rows.map(([,d]) => d.policy_candidates.phase3p_original_unmodified.candidate_episode_starts));
    $('bars').innerHTML = rows.map(([day,d]) => {
      const original = d.policy_candidates.phase3p_original_unmodified.candidate_episode_starts;
      const confirmed = d.policy_candidates.sharpness_3_consecutive.candidate_episode_starts;
      return `<div class="bar-row"><div class="bar-label">${escape(day.toUpperCase())}</div><div><div class="bar-track"><div class="bar" style="width:${100*original/max}%"></div></div><div class="bar-track" style="margin-top:4px"><div class="bar secondary" style="width:${100*confirmed/max}%"></div></div></div><div class="bar-value">${original} / ${confirmed}</div></div>`;
    }).join('') + '<div class="legend"><span><i></i>Original</span><span><i class="dark"></i>3 consecutive</span></div>';
    const eventContext = data.annotated_event_window_evidence;
    $('event-stats').innerHTML = eventContext ? ['day3','day4'].map(day => {
      const e = eventContext.days[day];
      const blur = e.defocused;
      const moved = e.moved;
      return `<div class="event-group"><div class="event-day">${escape(day.toUpperCase())}</div><div><strong>${blur.windows_with_any_original_candidate_inside_target}/${blur.selected_windows}</strong><span>annotated defocus windows with candidate</span></div><div><strong>${moved.windows_with_any_original_candidate_inside_target}/${moved.selected_windows}</strong><span>annotated moved windows with candidate</span></div></div>`;
    }).join('') : '<p class="footnote">No optional Phase3P annotated event report supplied.</p>';
    $('integrity').innerHTML = [
      ['Source video identity', 'SHA-256 recorded from Phase3R/3S; mounted AVI cannot be called verified unless hashed equal'],
      ['Physical scene ground truth', 'Not available. No independent validation of focus, obstruction or camera movement'],
      ['Production release', 'Blocked. No operational alerts, recovery or reference resets authorized']
    ].map(([title, body]) => `<div><strong>${escape(title)}</strong><p>${escape(body)}</p></div>`).join('');
    $('limits').innerHTML = data.limitations.map(line => `<li>${escape(line)}</li>`).join('');
    renderTable();
  };
  const renderConcordance = d => {
    const wrap = $('signal-comparison');
    if(!wrap || !d) return;
    const counts = d.overall_concordance;
    const groups = [
      ['CANDIDATE_AND_SPARSE_CHANGE','Candidate + sparse change'],
      ['CANDIDATE_WITHOUT_SPARSE_CHANGE','Candidate, no sparse change'],
      ['NONCANDIDATE_WITH_SPARSE_CHANGE','No candidate, sparse change'],
      ['NEITHER_RESEARCH_CUE','Neither cue observed']
    ];
    wrap.innerHTML = groups.map(([key,label])=>
      `<div class="event-group"><strong>${comma(counts[key])}</strong><span>${escape(label)}</span></div>`
    ).join('') +
    `<div class="event-group"><strong>${comma(d.geometric_coverage.unknown_windows)}/40</strong>`+
    `<span>Geometric proxy unavailable</span></div>`;
  };
  fetch('/api/concordance', {cache:'no-store'}).then(r => {
    if (r.status === 404) return null;
    if (!r.ok) throw Error('Signal comparison unavailable');
    return r.json();
  }).then(result => {
    if (result) renderConcordance(result);
    else $('signal-comparison').textContent =
      'Complete, source-audited 40-window AVI feature data is required before comparison.';
  }).catch(e=>{$('signal-comparison').textContent='Signal comparison unavailable: '+e.message});
  for(const id of ['day','signal','filter']) $(id).addEventListener(id==='filter'?'input':'change', () => report && renderTable());
  fetch('/api/report', {cache:'no-store'}).then(r => {if (!r.ok) throw Error('Could not load research report');return r.json()}).then(render).catch(e => {$('state').textContent = 'Research report unavailable: ' + e.message;});

  fetch('/api/product-readiness', {cache:'no-store'}).then(r => {
    if (!r.ok) throw Error('Source acceptance receipt missing');
    return r.json();
  }).then(d => {
    if (d.production_qualified !== false || !d.source_continuity) throw Error('Invalid source acceptance state');
    const stats = [
      ['Research system', d.software_readiness === 'COMPLETE_FOR_READ_ONLY_RESEARCH' ? 'Verified' : 'Unavailable'],
      ['Deployment', 'Field validation pending'],
      ['Source clip integrity', d.reproduced_research.drive_labeled_clips.clips + '/14 pinned clips'],
      ['Frame evidence', d.reproduced_research.sparse_video_frames + ' sampled frames']
    ];
    $('readiness-summary').innerHTML = stats.map(([label,val]) =>
      `<div class="event-group"><strong>${escape(val)}</strong><span>${escape(label)}</span></div>`
    ).join('');
    $('readiness-blockers').innerHTML = (d.release_blockers || [])
      .map(s => `<li>${escape(s)}</li>`).join('');
  }).catch(e => {
    $('readiness-summary').textContent = 'Acceptance is unavailable: ' + e.message;
  });

  fetch('/api/external-scene-probe',{cache:'no-store'}).then(r => r.ok ? r.json() : null).then(d=>{
    if (!d) { $('unlabeled-summary').textContent='No additional scene measurements configured.';return; }
    const entries = [
      [d.videos.length,'unlabeled recording contexts'],
      [d.total_frames_decoded,'fixed-time source samples'],
      [d.total_numerical_candidate_positions,'numerical cue samples; NOT false alerts'],
      [d.total_unknown_geometry_positions,'registration-unknown samples']
    ];
    $('unlabeled-summary').innerHTML = entries.map(([value,label])=>
       `<div class="event-group"><strong>${escape(value)}</strong><span>${escape(label)}</span></div>`
    ).join('');
  }).catch(e=>{$('unlabeled-summary').textContent='Scene comparison unavailable: '+e.message});

  fetch('/api/clip-diagnostics', {cache:'no-store'}).then(r => r.ok ? r.json() : null).then(d => {
    const head=$('clips-summary'), table=$('clips-table');
    if(!d){head.textContent='Clip numerical diagnostics are not configured.';return;}
    const t=d.comparison_against_existing_development_annotations;
    head.innerHTML=[
      [d.clips_evaluated + '/' + d.clips_expected,'labeled Drive clips evaluated'],
      [d.sampled_frames,'sampled source frames'],
      [t.TP + '/' + (t.TP+t.FN),'annotated event samples with numeric proxy'],
      [t.FP + '/' + (t.FP+t.TN),'other samples with numeric proxy']
    ].map(([n,name]) => `<div class="event-group"><strong>${escape(n)}</strong><span>${escape(name)}</span></div>`).join('');
    table.innerHTML=d.clips.map(c=>{
      const t=c.numeric_count_table_vs_existing_annotations;
      return `<tr><td>${escape(c.name)}</td><td>${escape(c.annotation_class)}</td><td>${c.sampled_frames}</td>`+
        `<td><span class="pill">${t.TP}</span></td><td>${t.FN}</td><td>${t.FP}</td>`+
        `<td>${c.exploratory_localized_change_samples||0}</td>`+
        `<td>${c.exploratory_registered_global_shift_samples||0}</td>`+
        `<td>${c.unreliable_geometric_registration_samples||0}</td></tr>`;
    }).join('');
  }).catch(e=>{$('clips-summary').textContent='No verified clip benchmark: '+e.message});
})();
