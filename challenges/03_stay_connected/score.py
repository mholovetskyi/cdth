#!/usr/bin/env python3
"""Stay Connected (challenge 03): scoring for tasks 3A, 3B and 3C.

  python score.py states  --submission submissions/epoch_states.csv         --labels  <epoch labels csv>
  python score.py sources --submission submissions/interference_sources.csv --events  <interference events csv>

3A  epoch_states.csv: timestamp, receiver_id, state [, est_lat, est_lon]
    state is one of nominal, natural, jamming, spoofing; one row per (timestamp, receiver_id) epoch.
    Score: macro F1 = the average of the four per-state F1 scores (higher is better).
    A labelled epoch with no row in the submission counts as wrong. A state that never occurs in the
    labels and is never predicted is left out of the average; one that is predicted but never occurs
    scores F1 = 0.
3C  (optional, same file) for epochs whose true state is spoofing: distance between est_lat/est_lon
    and the true position. Score: median error in metres (lower is better). A missing estimate
    (no row, no est_lat/est_lon columns, or an empty value) counts as 10,000 m.
3B  interference_sources.csv: kind, start, end, lat, lon
    kind is jamming or spoofing; lat/lon is your best estimate of where the source is at the middle
    of the event. A submitted event can match a true event of the same kind when their time spans
    overlap, with up to 1 h of gap allowed. Matching is one-to-one, greedy, largest overlap first.
    Scores: mean location error in km over the true events (primary, lower is better; a true event
    with no match counts as 50 km, and matched errors are capped at 50 km) and detection F1 (higher is better).

Only the epochs and events in the labels/events file are scored, so you can score a validation slice
cut from labels_train/ exactly the way the organizers score the hidden test days.
Natural events in the events file are ignored by 3B. Extra columns in a submission are ignored.
Times are ISO 8601 UTC (e.g. 2025-10-11T06:00:00Z); times without a zone are read as UTC.
Prints a JSON summary. Needs only numpy and pandas. Import it to use score_states() / score_sources().
"""
import argparse
import json
import os
import sys
import warnings as _warnings

import numpy as np
import pandas as pd

STATES = ['nominal', 'natural', 'jamming', 'spoofing']
SOURCE_KINDS = ['jamming', 'spoofing']
MISSING_ESTIMATE_M = 10_000.0      # 3C: no position estimate for a spoofed epoch
UNMATCHED_KM = 50.0                # 3B: a true event that nobody found
SLACK_S = 3600                     # 3B: allowed gap between submitted and true time spans
EARTH_R_M = 6_371_000.0


class ScoreError(ValueError):
    """A submission, labels or events file that cannot be scored. The message says why."""


# ------------------------------------------------------------------ helpers
def _load(x, what):
    if isinstance(x, pd.DataFrame):
        df = x.copy()
    elif isinstance(x, (str, os.PathLike)):
        if not os.path.isfile(x):
            raise ScoreError(f'{what} file not found: {x}')
        try:
            df = pd.read_csv(x)
        except Exception as e:  # empty file, bad encoding, ...
            raise ScoreError(f'could not read {what} file {x}: {e}') from None
    else:
        raise ScoreError(f'{what} must be a pandas DataFrame or the path to a CSV file')
    df.columns = [str(c).strip() for c in df.columns]
    return df.reset_index(drop=True)


def _require(df, cols, what):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ScoreError(f'{what} is missing column(s) {missing}; it has {list(df.columns)}')


def _text(s):
    return s.astype(object).where(s.notna(), '').astype(str).str.strip()


def _seconds(s, what, col):
    """Times -> integer seconds since 1970-01-01 UTC."""
    try:
        t = pd.to_datetime(s, utc=True, format='ISO8601')
    except (TypeError, ValueError):          # not all ISO 8601, or pandas < 2.0: fall back to the general parser
        with _warnings.catch_warnings():
            _warnings.simplefilter('ignore')
            t = pd.to_datetime(s, utc=True, errors='coerce')
    bad = t.isna().to_numpy()
    if bad.any():
        first = s[bad].iloc[0]
        raise ScoreError(f'{what}: {int(bad.sum())} value(s) in column {col!r} are not valid times '
                         f'(first: {first!r}); use ISO 8601 such as 2025-10-11T06:00:00Z')
    return np.round((t - pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds().to_numpy()).astype('int64')


def _numbers(df, cols, what):
    out = []
    for c in cols:
        v = pd.to_numeric(df[c], errors='coerce')
        bad = v.isna() & df[c].notna() & (_text(df[c]) != '')
        if bad.any():
            raise ScoreError(f'{what}: column {c!r} has non-numeric values (first: {df[c][bad].iloc[0]!r})')
        out.append(v.to_numpy(dtype=float))
    lat, lon = out
    if (np.abs(lat[~np.isnan(lat)]) > 90).any():
        raise ScoreError(f'{what}: {cols[0]!r} has values outside -90..90 (did you swap latitude and longitude?)')
    if (np.abs(lon[~np.isnan(lon)]) > 180).any():
        raise ScoreError(f'{what}: {cols[1]!r} has values outside -180..180')
    return lat, lon


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (vectorised)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lon2) - np.asarray(lon1)) / 2) ** 2
    return 2 * EARTH_R_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _r(x, nd):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def _epoch_keys(df, what):
    t = _seconds(df['timestamp'], what, 'timestamp')
    r = _text(df['receiver_id']).str.upper().to_numpy()
    keys = pd.DataFrame({'_t': t, '_r': r})
    dup = keys.duplicated().to_numpy()
    if dup.any():
        i = int(np.flatnonzero(dup)[0])
        raise ScoreError(f'{what} has {int(dup.sum())} duplicate row(s) for the same timestamp and receiver_id '
                         f'(first: {df["timestamp"].iloc[i]} {df["receiver_id"].iloc[i]}); keep one row per epoch')
    return keys


def _states(s, what):
    v = _text(s).str.lower()
    bad = ~v.isin(STATES)
    if bad.any():
        raise ScoreError(f'{what}: {int(bad.sum())} row(s) have an unknown state (first: {s[bad].iloc[0]!r}); '
                         f'allowed: {", ".join(STATES)}')
    return v.to_numpy()


# ------------------------------------------------------------------ tasks 3A + 3C
def score_states(sub, labels):
    """Score an epoch_states submission (3A, plus 3C when est_lat/est_lon are present).

    sub, labels: DataFrames or CSV paths. labels needs timestamp, receiver_id, state (and true_lat,
    true_lon for 3C). Only epochs in `labels` are scored. Returns a dict (see the JSON printed by the CLI)."""
    S, L = _load(sub, 'submission'), _load(labels, 'labels')
    _require(S, ['timestamp', 'receiver_id', 'state'], 'submission')
    _require(L, ['timestamp', 'receiver_id', 'state'], 'labels')
    if ('est_lat' in S.columns) != ('est_lon' in S.columns):
        raise ScoreError('submission has only one of est_lat / est_lon; give both or neither')
    warnings = []
    kS, kL = _epoch_keys(S, 'submission'), _epoch_keys(L, 'labels')
    kS['pred'] = _states(S['state'], 'submission')
    kL['true'] = _states(L['state'], 'labels')
    has_est = 'est_lat' in S.columns
    if has_est:
        kS['est_lat'], kS['est_lon'] = _numbers(S, ['est_lat', 'est_lon'], 'submission')
    has_truth_pos = 'true_lat' in L.columns and 'true_lon' in L.columns
    if has_truth_pos:
        kL['true_lat'], kL['true_lon'] = _numbers(L, ['true_lat', 'true_lon'], 'labels')

    M = kL.merge(kS, on=['_t', '_r'], how='left', sort=False)
    n = len(M)
    if n == 0:
        raise ScoreError('the labels file has no epochs to score')
    y = M['true'].to_numpy()
    p = M['pred'].fillna('(missing)').to_numpy(dtype=object)
    n_missing = int((p == '(missing)').sum())
    n_extra = len(kS) - (n - n_missing)
    if n_missing == n:
        warnings.append('no submission row matches a labelled epoch: check the time window, the timestamp format '
                        'and the receiver ids')
    elif n_missing:
        warnings.append(f'{n_missing} labelled epoch(s) have no row in the submission; they count as wrong')
    if n_extra:
        warnings.append(f'{n_extra} submission row(s) are not in the labels and were ignored')

    per_state, f1s = {}, []
    for c in STATES:
        tp = int(((y == c) & (p == c)).sum())
        fp = int(((y != c) & (p == c)).sum())
        fn = int(((y == c) & (p != c)).sum())
        if tp + fp + fn == 0:
            f1 = None                                   # never occurs, never predicted: not scored
        else:
            f1 = 2 * tp / (2 * tp + fp + fn)
            f1s.append(f1)
        per_state[c] = dict(f1=_r(f1, 4), precision=_r(tp / (tp + fp), 4) if tp + fp else None,
                            recall=_r(tp / (tp + fn), 4) if tp + fn else None, support=tp + fn, predicted=tp + fp)
    absent = [c for c in STATES if per_state[c]['support'] == 0]
    if absent:
        warnings.append(f'state(s) {absent} never occur in these labels: each is left out of macro F1 if you never '
                        f'predict it, and scores F1 = 0 if you do (here macro F1 averages {len(f1s)} state(s))')
    confusion = {c: {k: int(((y == c) & (p == k)).sum()) for k in STATES + ['(missing)']} for c in STATES}

    res3a = dict(macro_f1=_r(float(np.mean(f1s)), 4) if f1s else None,
                 accuracy=_r(float((y == p).mean()), 4),
                 per_state=per_state,
                 epochs_scored=n, epochs_missing=n_missing, submission_rows_ignored=int(n_extra),
                 confusion_true_by_pred=confusion)

    # 3C: where is it really? (only epochs whose true state is spoofing)
    spoof = y == 'spoofing'
    ns = int(spoof.sum())
    if ns == 0:
        res3c = dict(median_error_m=None, spoofing_epochs=0, note='no spoofing epochs in these labels')
    elif not has_truth_pos:
        res3c = dict(median_error_m=None, spoofing_epochs=ns, note='labels have no true_lat/true_lon')
    else:
        if has_est:
            err = haversine_m(M['est_lat'].to_numpy(float)[spoof], M['est_lon'].to_numpy(float)[spoof],
                              M['true_lat'].to_numpy(float)[spoof], M['true_lon'].to_numpy(float)[spoof])
        else:
            err = np.full(ns, np.nan)
        no_est = np.isnan(err)
        err = np.where(no_est, MISSING_ESTIMATE_M, err)
        res3c = dict(median_error_m=_r(np.median(err), 1), mean_error_m=_r(err.mean(), 1),
                     p90_error_m=_r(np.percentile(err, 90), 1), spoofing_epochs=ns,
                     epochs_without_estimate=int(no_est.sum()))
        if not has_est:
            res3c['note'] = 'submission has no est_lat/est_lon columns; every spoofed epoch counts as 10,000 m'
    return {'3A': res3a, '3C': res3c, 'warnings': warnings}


# ------------------------------------------------------------------ task 3B
def score_sources(sub, events):
    """Score an interference_sources submission (3B) against an interference events file.

    sub, events: DataFrames or CSV paths. Only jamming/spoofing events in `events` are scored.
    Returns a dict (see the JSON printed by the CLI)."""
    S, E = _load(sub, 'submission'), _load(events, 'events')
    _require(S, ['kind', 'start', 'end', 'lat', 'lon'], 'submission')
    _require(E, ['kind', 'start', 'end', 'lat_at_midpoint', 'lon_at_midpoint'], 'events')
    warnings = []
    sk = _text(S['kind']).str.lower()
    bad = ~sk.isin(SOURCE_KINDS)
    if bad.any():
        raise ScoreError(f'submission: {int(bad.sum())} row(s) have an unknown kind (first: {S["kind"][bad].iloc[0]!r}); '
                         f'allowed: jamming, spoofing')
    s_kind = sk.to_numpy()
    s0, s1 = _seconds(S['start'], 'submission', 'start'), _seconds(S['end'], 'submission', 'end')
    if (s1 < s0).any():
        i = int(np.flatnonzero(s1 < s0)[0])
        raise ScoreError(f'submission row {i}: end ({S["end"].iloc[i]}) is before start ({S["start"].iloc[i]})')
    s_lat, s_lon = _numbers(S, ['lat', 'lon'], 'submission')
    if np.isnan(s_lat).any() or np.isnan(s_lon).any():
        warnings.append('some submitted events have no lat/lon; if matched they count as 50 km')

    ek = _text(E['kind']).str.lower()
    T = E[ek.isin(SOURCE_KINDS).to_numpy()].reset_index(drop=True)
    t_kind = ek[ek.isin(SOURCE_KINDS)].to_numpy()
    t0, t1 = _seconds(T['start'], 'events', 'start'), _seconds(T['end'], 'events', 'end')
    t_lat, t_lon = _numbers(T, ['lat_at_midpoint', 'lon_at_midpoint'], 'events')
    if np.isnan(t_lat).any() or np.isnan(t_lon).any():
        raise ScoreError('events: a jamming/spoofing event has no lat_at_midpoint / lon_at_midpoint')
    ids = _text(T['event_id']).to_numpy() if 'event_id' in T.columns else np.array([f'event_{i}' for i in range(len(T))])
    nt, ns = len(T), len(S)

    # candidate pairs: same kind and a gap of at most 1 h (overlap < 0 means a gap)
    ti, si = np.meshgrid(np.arange(nt), np.arange(ns), indexing='ij')
    ti, si = ti.ravel(), si.ravel()
    overlap = np.minimum(t1[ti], s1[si]) - np.maximum(t0[ti], s0[si])
    ok = (t_kind[ti] == s_kind[si]) & (overlap >= -SLACK_S)
    ti, si, overlap = ti[ok], si[ok], overlap[ok]
    dist = haversine_m(s_lat[si], s_lon[si], t_lat[ti], t_lon[ti]) / 1000.0
    order = np.lexsort((si, ti, np.where(np.isnan(dist), np.inf, dist), -overlap))   # largest overlap first
    match_t, used_s = {}, set()
    for k in order:
        a, b = int(ti[k]), int(si[k])
        if a in match_t or b in used_s:
            continue
        match_t[a] = (b, overlap[k], dist[k])
        used_s.add(b)

    per_event, errs = [], np.full(nt, UNMATCHED_KM)
    for a in range(nt):
        row = dict(event_id=str(ids[a]), kind=str(t_kind[a]), matched=a in match_t)
        if a in match_t:
            b, ov, d = match_t[a]
            errs[a] = UNMATCHED_KM if np.isnan(d) else min(d, UNMATCHED_KM)     # a wild guess never scores worse than a miss
            row.update(submission_index=b, overlap_h=_r(ov / 3600, 2), error_km=_r(errs[a], 3))
        else:
            row.update(submission_index=None, overlap_h=None, error_km=None)
        row['counted_km'] = _r(errs[a], 3)
        per_event.append(row)

    def block(mask_t, mask_s):
        tp = sum(1 for a in np.flatnonzero(mask_t) if a in match_t)
        n_t, n_s = int(mask_t.sum()), int(mask_s.sum())
        return dict(mean_location_error_km=_r(errs[mask_t].mean(), 3) if n_t else None,
                    detection_f1=_r(2 * tp / (n_t + n_s), 4) if n_t + n_s else None,
                    precision=_r(tp / n_s, 4) if n_s else None, recall=_r(tp / n_t, 4) if n_t else None,
                    true_events=n_t, submitted_events=n_s, matched=tp)

    res = block(np.ones(nt, bool), np.ones(ns, bool))
    res['by_kind'] = {k: block(t_kind == k, s_kind == k) for k in SOURCE_KINDS}
    res['events'] = per_event
    if nt == 0:
        warnings.append('the events file has no jamming/spoofing events; location error cannot be computed')
    return {'3B': res, 'warnings': warnings}


# ------------------------------------------------------------------ command line
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='task', required=True)
    a = sub.add_parser('states', help='score task 3A (and 3C when est_lat/est_lon are given)')
    a.add_argument('--submission', default=os.path.join('submissions', 'epoch_states.csv'))
    a.add_argument('--labels', required=True, help='epoch labels CSV: timestamp, receiver_id, state, true_lat, true_lon')
    b = sub.add_parser('sources', help='score task 3B')
    b.add_argument('--submission', default=os.path.join('submissions', 'interference_sources.csv'))
    b.add_argument('--events', required=True, help='interference events CSV: event_id, kind, start, end, lat_at_midpoint, lon_at_midpoint')
    args = ap.parse_args(argv)
    try:
        res = score_states(args.submission, args.labels) if args.task == 'states' else score_sources(args.submission, args.events)
    except ScoreError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    for w in res['warnings']:
        print(f'warning: {w}', file=sys.stderr)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
