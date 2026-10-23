import React, { useEffect, useState } from 'react';
import { requestJson } from '../../services/httpClient.js';
import RegisteredStatistics from '../admin-normalization/RegisteredStatistics.jsx';
import BPSQuestionSearch from './BPSQuestionSearch.jsx';

export default function BPSStatisticsSearch() {
  const [available, setAvailable] = useState(false);
  const [opened, setOpened] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    requestJson('/search/bps/statistics/status', { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setAvailable(data.available === true); })
      .catch(() => {});
    return () => controller.abort();
  }, []);
  if (!available) return null;
  return <details onToggle={event => setOpened(event.currentTarget.open)}
    style={{ border: '1px solid #dedede', borderRadius: 14, padding: 16, background: '#fff' }}>
    <summary style={{ cursor: 'pointer', fontWeight: 700 }}>Cari angka dan tren BPS</summary>
    {opened && <><BPSQuestionSearch /><RegisteredStatistics base="/search/bps/statistics" /></>}
  </details>;
}
