import React, { useCallback, useEffect, useMemo, useState } from 'react';

const splitTopics = value => Array.from(new Set(
  String(value || '')
    .split(/[\n,]+/)
    .map(item => item.trim())
    .filter(Boolean)
    .map(item => item.startsWith('/') ? item : `/${item}`)
));

const formatTime = value => {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return '';
  return new Date(seconds * 1000).toLocaleString('ko-KR');
};

async function requestJson(url, options) {
  const response = await fetch(url, options);
  let body = {};
  try {
    body = await response.json();
  } catch (_error) {
    body = { message: '서버 응답을 해석할 수 없습니다.' };
  }
  if (!response.ok || body.success === false) {
    const error = new Error(body.message || `요청 실패 (${response.status})`);
    error.body = body;
    throw error;
  }
  return body;
}

export default function SnapshotControl() {
  const [status, setStatus] = useState({
    available: false,
    recording: false,
    writing: false,
    pending: false,
    active_topics: [],
    dynamic_topics: [],
    last_result: {},
  });
  const [topicInput, setTopicInput] = useState('');
  const [label, setLabel] = useState('');
  const [outputDirectory, setOutputDirectory] = useState(null);
  const [lookbackSeconds, setLookbackSeconds] = useState('300');
  const [message, setMessage] = useState('Snapshot 서비스 연결 확인 중…');
  const [topicPending, setTopicPending] = useState(false);
  const [writePending, setWritePending] = useState(false);
  const [confirmWrite, setConfirmWrite] = useState(false);

  const refresh = useCallback(async (quiet = false) => {
    try {
      const body = await requestJson('/api/admin/snapshot/status');
      setStatus(body);
      if (!quiet) {
        setMessage(body.available
          ? (body.recording
            ? ''
            : '메시지 버퍼링이 일시 정지되어 있습니다.')
          : 'Snapshot 서비스에 연결할 수 없습니다.');
      }
    } catch (error) {
      setStatus(current => ({ ...current, available: false }));
      if (!quiet) setMessage(error.message);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const run = async quiet => {
      if (mounted) await refresh(quiet);
    };
    run(false);
    const timer = window.setInterval(() => run(true), 3000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [refresh]);

  const dynamicNames = useMemo(
    () => (status.dynamic_topics || []).map(item => item.name).sort(),
    [status.dynamic_topics]
  );
  const busy = Boolean(writePending || status.pending || status.writing);
  const numericLookback = Number(lookbackSeconds);
  const lookbackValid = Number.isFinite(numericLookback)
    && numericLookback >= 1
    && numericLookback <= 300;

  const addTopics = async () => {
    const topics = splitTopics(topicInput);
    if (!topics.length || topicPending || busy) {
      if (!topics.length) setMessage('추가로 버퍼링할 토픽을 입력해 주세요.');
      return;
    }
    setTopicPending(true);
    setMessage('추가 토픽 구독을 설정하는 중…');
    try {
      const body = await requestJson('/api/admin/snapshot/topics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topics }),
      });
      setTopicInput('');
      setMessage(body.message || '추가 토픽의 버퍼링을 시작했습니다.');
      await refresh(true);
    } catch (error) {
      const rejected = error.body?.rejected_topics || [];
      setMessage(rejected.length
        ? `추가할 수 없는 토픽: ${rejected.join(', ')}`
        : error.message);
    } finally {
      setTopicPending(false);
    }
  };

  const removeTopic = async topic => {
    if (topicPending || busy) return;
    setTopicPending(true);
    setMessage(`${topic} 토픽의 버퍼링을 중지하는 중…`);
    try {
      const body = await requestJson('/api/admin/snapshot/topics', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topics: [topic] }),
      });
      setMessage(body.message || '추가 토픽의 버퍼링을 중지했습니다.');
      await refresh(true);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setTopicPending(false);
    }
  };

  const writeSnapshot = async () => {
    if (!lookbackValid) {
      setMessage('저장 범위는 1초에서 300초 사이로 입력해 주세요.');
      return;
    }
    if (!confirmWrite) {
      setConfirmWrite(true);
      setMessage(`최근 ${numericLookback}초의 버퍼를 rosbag으로 저장합니다. 계속하려면 저장 버튼을 한 번 더 눌러 주세요.`);
      return;
    }
    if (busy || !status.available) return;
    setConfirmWrite(false);
    setWritePending(true);
    setMessage('rosbag 스냅샷을 저장하는 중…');
    try {
      const body = await requestJson('/api/admin/snapshot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label,
          topics: [],
          output_directory: outputDirectory ?? status.output_directory ?? '',
          lookback_seconds: numericLookback,
        }),
      });
      setLabel('');
      setMessage(body.message || `저장 완료: ${body.path}`);
      setStatus(current => ({ ...current, last_result: body }));
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWritePending(false);
      await refresh(true);
    }
  };

  const lastResult = status.last_result || {};
  return (
    <section className="snapshot-control-card" aria-label="ROS Snapshot">
      <div className="snapshot-control-heading">
        <div>
          <div className="snapshot-control-title">ROSBAG Snapshot</div>
          <div className="snapshot-control-help">
            버퍼링 중인 ROS 토픽의 최근 데이터를 하나의 rosbag으로 저장합니다.
          </div>
        </div>
        <span className={`snapshot-state ${status.available ? (busy ? 'busy' : 'ready') : 'offline'}`}>
          {status.available
            ? (busy ? '저장 중' : (status.recording ? '버퍼링 중' : '일시 정지'))
            : '연결 안 됨'}
        </span>
      </div>

      <div className="snapshot-summary-row">
        <span>버퍼링 토픽 <strong>{(status.active_topics || []).length}</strong>개</span>
        <span>추가 토픽 <strong>{dynamicNames.length}</strong>개</span>
        {Number.isFinite(status.free_space_mb) && (
          <span>기본 경로 여유 <strong>{Math.round(status.free_space_mb / 1024)}</strong>GB</span>
        )}
      </div>

      <label className="snapshot-field-label" htmlFor="snapshot-topic-input">
        추가 토픽 — 입력 후 ‘버퍼링 시작’을 눌러 주세요
      </label>
      <div className="snapshot-topic-entry">
        <textarea
          id="snapshot-topic-input"
          value={topicInput}
          onChange={event => setTopicInput(event.target.value)}
          placeholder={'/example/topic\n/sensing/radar/right1/range'}
          rows={3}
          disabled={!status.available || topicPending || busy}
        />
        <button
          type="button"
          onClick={addTopics}
          disabled={!status.available || topicPending || busy || !splitTopics(topicInput).length}
        >
          {topicPending ? '적용 중…' : '버퍼링 시작'}
        </button>
      </div>

      {dynamicNames.length > 0 && (
        <div className="snapshot-topic-chips" aria-label="동적 추가 토픽">
          {dynamicNames.map(topic => (
            <button
              type="button"
              key={topic}
              onClick={() => removeTopic(topic)}
              disabled={topicPending || busy}
              title="이 런타임 토픽의 버퍼링 중지"
            >
              {topic}<span aria-hidden="true"> ×</span>
            </button>
          ))}
        </div>
      )}

      <div className="snapshot-directory-row">
        <label htmlFor="snapshot-directory-input">저장 폴더</label>
        <input
          id="snapshot-directory-input"
          type="text"
          value={outputDirectory ?? status.output_directory ?? ''}
          maxLength={1024}
          onChange={event => setOutputDirectory(event.target.value)}
          placeholder="예: /home/avg/Data/snapshots"
          disabled={busy}
          spellCheck={false}
        />
        <button
          type="button"
          className="reset-directory"
          onClick={() => setOutputDirectory(null)}
          disabled={busy || outputDirectory === null}
          title="설정된 기본 저장 폴더로 되돌리기"
        >
          기본값 복원
        </button>
        <small>로봇(서버) 기준 경로입니다. 절대 경로 또는 ~로 시작하는 경로를 입력하세요.</small>
      </div>

      <div className="snapshot-lookback-row">
        <label htmlFor="snapshot-lookback-input">저장 범위</label>
        <span className="snapshot-lookback-input">
          최근
          <input
            id="snapshot-lookback-input"
            type="number"
            min="1"
            max="300"
            step="1"
            value={lookbackSeconds}
            onChange={event => {
              setLookbackSeconds(event.target.value);
              setConfirmWrite(false);
            }}
            disabled={busy}
          />
          초
        </span>
        <small>최대 300초이며, 토픽별로 현재 버퍼에 남아 있는 범위 안에서 저장됩니다.</small>
      </div>

      <div className="snapshot-save-row">
        <label htmlFor="snapshot-label-input">파일 이름 태그 (선택)</label>
        <input
          id="snapshot-label-input"
          type="text"
          value={label}
          maxLength={48}
          onChange={event => setLabel(event.target.value)}
          placeholder="예: 우측 레이더 점검"
          disabled={busy}
        />
        <button
          type="button"
          className={confirmWrite ? 'confirm' : ''}
          onClick={writeSnapshot}
          disabled={!status.available || busy || !lookbackValid}
        >
          {busy ? '저장 중…' : (confirmWrite ? '확인 후 저장' : '스냅샷 저장')}
        </button>
        {confirmWrite && (
          <button type="button" className="cancel" onClick={() => setConfirmWrite(false)}>
            취소
          </button>
        )}
        <small>bag 내부에 TXT가 생성되지 않으며, 저장 폴더 이름 뒤에 붙습니다.</small>
      </div>

      <div className="snapshot-status-message" role="status">{message}</div>
      {lastResult.path && (
        <div className={`snapshot-last-result ${lastResult.success ? 'success' : 'failure'}`}>
          <span>{lastResult.success ? '최근 저장' : '최근 저장 시도'}</span>
          <code>{lastResult.path}</code>
          {lastResult.completed_at && <time>{formatTime(lastResult.completed_at)}</time>}
        </div>
      )}
    </section>
  );
}
