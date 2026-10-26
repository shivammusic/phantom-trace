const SAMPLE = `2026-10-01T09:04:12Z | deploy-api | TLS certificate expired while contacting artifact registry
2026-10-03T14:18:42Z | deploy-worker | artifact registry rejected connection because the certificate expired
2026-10-08T07:51:03Z | release-web | x509 certificate has expired for registry.internal
2026-10-10T16:20:19Z | build-api | no space left on device while extracting image layers
2026-10-12T11:02:07Z | build-worker | container image extraction failed: disk is full
2026-10-18T18:44:53Z | release-api | runner ran out of disk space while unpacking the image
2026-10-21T13:36:20Z | deploy-web | required secret DATABASE_URL was not available
2026-10-22T08:13:09Z | deploy-api | deployment stopped because DATABASE_URL is missing
2026-10-24T20:01:33Z | test-web | accessibility suite found a missing form label`;

const $ = id => document.getElementById(id);
$('logs').value = SAMPLE;
$('sample').onclick = () => { $('logs').value = SAMPLE; };
$('threshold').oninput = event => { $('threshold-value').value = Number(event.target.value).toFixed(2); };

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function render(data) {
  $('summary').innerHTML = `<strong>${data.recurring_ghosts}</strong> recurring patterns · <strong>${data.event_count}</strong> events`;
  $('clusters').innerHTML = data.clusters.map((cluster, index) => `
    <article class="cluster ${cluster.status}">
      <div class="score"><span>${cluster.haunting_score}</span><small>HAUNTING<br>SCORE</small></div>
      <div class="cluster-body">
        <div class="cluster-meta"><span>GHOST ${String(index + 1).padStart(2, '0')}</span><span class="status">${cluster.status}</span></div>
        <h3>${escapeHtml(cluster.title)}</h3>
        <p>${cluster.event_count} event${cluster.event_count === 1 ? '' : 's'} across ${cluster.sources.length} source${cluster.sources.length === 1 ? '' : 's'} · ${escapeHtml(cluster.sources.join(', '))}</p>
        <details ${index === 0 ? 'open' : ''}><summary>Inspect source evidence</summary>
          <ol>${cluster.evidence.map(item => `<li><time>${escapeHtml(item.timestamp)}</time><b>${escapeHtml(item.source)}</b><span>${escapeHtml(item.message)}</span></li>`).join('')}</ol>
        </details>
      </div>
    </article>`).join('');
  $('results').classList.remove('hidden');
  $('results').scrollIntoView({behavior: 'smooth'});
}

$('analyze').onclick = async () => {
  $('error').textContent = '';
  $('analyze').disabled = true;
  $('analyze').textContent = 'Tracing locally…';
  try {
    const response = await fetch('/api/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({logs:$('logs').value, threshold:Number($('threshold').value)})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Analysis failed.');
    render(data);
  } catch (error) {
    $('error').textContent = error.message;
  } finally {
    $('analyze').disabled = false;
    $('analyze').textContent = 'Trace recurring ghosts';
  }
};
