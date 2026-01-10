'use client';

import { useMemo, useState } from 'react';
import { apiFetch } from '@/lib/api';

type Visibility = 'physicians' | 'group';

const ASSET_CLASSES = [
  { value: 'self_storage', label: 'Self-Storage' },
  { value: 'multifamily', label: 'Multifamily' },
  { value: 'private_credit', label: 'Private Credit' },
  { value: 'equities', label: 'Equities' },
  { value: 'crypto', label: 'Crypto' },
  { value: 'other', label: 'Other' },
];

const STRATEGIES = [
  { value: 'core', label: 'Core' },
  { value: 'value_add', label: 'Value-Add' },
  { value: 'opportunistic', label: 'Opportunistic' },
  { value: 'development', label: 'Development' },
  { value: 'distressed', label: 'Distressed' },
  { value: 'other', label: 'Other' },
];

const QUESTION_OPTIONS = [
  'Validate assumptions',
  'Find risks I’m missing',
  'Evaluate sponsor',
  'Compare alternatives',
  'Diligence checklist',
];

export default function DealWizard() {
  const [step, setStep] = useState(1);

  const [title, setTitle] = useState('');
  const [visibility, setVisibility] = useState<Visibility>('physicians');
  const [assetClass, setAssetClass] = useState('self_storage');
  const [strategy, setStrategy] = useState('value_add');
  const [location, setLocation] = useState('');
  const [timeHorizonMonths, setTimeHorizonMonths] = useState<number | ''>('');

  const [thesis, setThesis] = useState('');
  const [questions, setQuestions] = useState<string[]>([]);
  const [questionsDetail, setQuestionsDetail] = useState('');
  const [agreed, setAgreed] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canNext = useMemo(() => {
    if (step === 1) return title.trim().length >= 3 && assetClass.length > 0 && strategy.length > 0;
    if (step === 2) return thesis.trim().length >= 30;
    if (step === 3) return true;
    if (step === 4) return agreed;
    return false;
  }, [step, title, assetClass, strategy, thesis, agreed]);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        title,
        visibility,
        deal: {
          asset_class: assetClass,
          strategy,
          location: location || null,
          time_horizon_months: timeHorizonMonths === '' ? null : timeHorizonMonths,
          thesis,
          user_questions: questions,
          questions_detail: questionsDetail || null,
          status: 'open',
        },
        auto_ai: true,
      };

      const res = await apiFetch('/api/deals', { method: 'POST', body: JSON.stringify(payload) });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.error || 'Failed to create deal');
      }
      const j = await res.json();
      // Prefer redirect if server sends it
      const dealId = j.deal_id || j.id;
      window.location.href = dealId ? `/deals/${dealId}` : '/deals';
    } catch (e: any) {
      setError(e?.message || 'Submit failed');
    } finally {
      setSubmitting(false);
    }
  }

  function toggleQuestion(q: string) {
    setQuestions((prev) => {
      if (prev.includes(q)) return prev.filter((x) => x !== q);
      if (prev.length >= 3) return prev; // cap
      return [...prev, q];
    });
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <h1>Post a Deal</h1>

      <div style={{ marginTop: 16 }}>
        <div>Step {step} of 4</div>
        <div style={{ marginTop: 12, padding: 12, border: '1px solid #333', borderRadius: 8 }}>
          {step === 1 && (
            <>
              <label>Title</label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} style={{ width: '100%' }} />

              <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
                <div style={{ flex: 1 }}>
                  <label>Asset class</label>
                  <select value={assetClass} onChange={(e) => setAssetClass(e.target.value)} style={{ width: '100%' }}>
                    {ASSET_CLASSES.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label>Strategy</label>
                  <select value={strategy} onChange={(e) => setStrategy(e.target.value)} style={{ width: '100%' }}>
                    {STRATEGIES.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
                <div style={{ flex: 2 }}>
                  <label>Location (optional)</label>
                  <input value={location} onChange={(e) => setLocation(e.target.value)} style={{ width: '100%' }} />
                </div>
                <div style={{ flex: 1 }}>
                  <label>Time horizon (months)</label>
                  <input
                    value={timeHorizonMonths}
                    onChange={(e) => setTimeHorizonMonths(e.target.value === '' ? '' : Number(e.target.value))}
                    style={{ width: '100%' }}
                    type="number"
                    min={0}
                  />
                </div>
              </div>

              <div style={{ marginTop: 12 }}>
                <label>Visibility</label>
                <select value={visibility} onChange={(e) => setVisibility(e.target.value as Visibility)} style={{ width: '100%' }}>
                  <option value="physicians">Physicians only</option>
                  <option value="group">Group (if applicable)</option>
                </select>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <label>Thesis (required)</label>
              <textarea
                value={thesis}
                onChange={(e) => setThesis(e.target.value)}
                style={{ width: '100%', minHeight: 160 }}
                placeholder="What’s the deal in ~3 sentences? What’s the edge? Why now?"
              />
              <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
                Minimum ~30 characters. Be concrete.
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <div>What do you want from the room? (pick up to 3)</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
                {QUESTION_OPTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => toggleQuestion(q)}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 999,
                      border: '1px solid #333',
                      background: questions.includes(q) ? '#222' : 'transparent',
                      color: 'inherit',
                      cursor: 'pointer',
                    }}
                    type="button"
                  >
                    {q}
                  </button>
                ))}
              </div>

              <div style={{ marginTop: 12 }}>
                <label>Specific questions (optional)</label>
                <textarea value={questionsDetail} onChange={(e) => setQuestionsDetail(e.target.value)} style={{ width: '100%', minHeight: 120 }} />
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <h3>Review</h3>
              <div><strong>{title}</strong></div>
              <div style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{thesis}</div>
              <div style={{ marginTop: 8 }}>Asking: {questions.join(', ') || '—'}</div>

              <div style={{ marginTop: 12 }}>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
                  Educational discussion only — not investment advice.
                </label>
              </div>

              <div style={{ marginTop: 12, fontSize: 12, opacity: 0.8 }}>
                On submit, the AI Analyst runs automatically and posts a versioned analysis to this deal.
              </div>
            </>
          )}
        </div>

        {error && <div style={{ marginTop: 12, color: 'tomato' }}>{error}</div>}

        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          {step > 1 && (
            <button type="button" onClick={() => setStep(step - 1)} disabled={submitting}>
              Back
            </button>
          )}
          {step < 4 && (
            <button type="button" onClick={() => setStep(step + 1)} disabled={!canNext || submitting}>
              Next
            </button>
          )}
          {step === 4 && (
            <button type="button" onClick={submit} disabled={!canNext || submitting}>
              {submitting ? 'Submitting…' : 'Submit & Run AI Analyst'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
