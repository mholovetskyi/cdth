#!/usr/bin/env python3
"""Eyes on the Sky - scoring for practice challenge 02 (tasks 2A, 2B, 2C).

  python score.py --submission submissions/tracks.csv --labels <labels.csv> [--out result.json]

Submission: one row per track, columns track_id, category, alert, operator_lat, operator_lon
  category                    drone | bird | manned | other
  alert                       1 = raise the alarm, 0 = no alarm
  operator_lat, operator_lon  estimated pilot position in decimal degrees (may be left blank)

Labels: same columns as labels_train/track_labels.csv. Participants pass a validation cut of
labels_train (for example the last training day); organizers pass the hidden test labels.
Only tracks that appear in the labels file are scored. A labelled track that is missing from the
submission counts as a wrong category, alert = 0 and a 5000 m operator error.

  2A  what is it       macro F1 over the categories (+ per-class table and confusion matrix)
  2B  raise the alarm  F1 of alert = 1 (+ precision, recall); the true alert is
                       category == drone AND authorized == False AND enters_alert_zone == True
  2C  find the pilot   median distance (m) between estimated and true operator position over
                       RF-controlled drones (autonomous_no_rf == False) whose true operator position
                       is known (+ share within 300 m); a blank estimate counts as 5000 m

Needs only numpy, pandas and the standard library. Also importable:
  from score import score_tracks;  result = score_tracks(sub_df_or_path, labels_df_or_path)
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd

CATEGORIES = ['drone', 'bird', 'manned', 'other']
SUB_COLUMNS = ['track_id', 'category', 'alert', 'operator_lat', 'operator_lon']
LABEL_COLUMNS = ['track_id', 'category', 'authorized', 'enters_alert_zone', 'operator_lat', 'operator_lon']
MISSING_ERROR_M = 5000.0
WITHIN_M = 300.0
EARTH_RADIUS_M = 6371008.8
_TRUE = {'true', 't', 'yes', 'y', '1', '1.0'}
_FALSE = {'false', 'f', 'no', 'n', '0', '0.0'}


class ScoreError(ValueError):
    """The submission or the labels cannot be scored (missing columns, unknown values, ...)."""


def _read(x, what):
    if isinstance(x, pd.DataFrame):
        return x.copy()
    try:
        return pd.read_csv(x, dtype={'track_id': str})
    except FileNotFoundError:
        raise ScoreError(f'{what} file not found: {x}') from None
    except pd.errors.EmptyDataError:
        raise ScoreError(f'{what} file is empty: {x}') from None


def _require(df, cols, what):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ScoreError(f"{what} is missing column(s): {', '.join(missing)}. "
                         f"Expected at least: {', '.join(cols)}")


def _examples(values, k=5):
    v = list(dict.fromkeys(str(x) for x in values))
    return ', '.join(v[:k]) + (' ...' if len(v) > k else '')


def _clean_ids(df, what):
    if df['track_id'].isna().any():
        raise ScoreError(f'{what} has {int(df.track_id.isna().sum())} row(s) with a blank track_id')
    df['track_id'] = df['track_id'].astype(str).str.strip()
    dup = df.track_id[df.track_id.duplicated()]
    if len(dup):
        raise ScoreError(f'{what} has duplicate track_id(s): {_examples(dup)} (one row per track, please)')
    return df


def _text(s):
    return s.astype('string').str.strip().str.lower()


def _mask(m):
    """Plain numpy-backed bool Series (missing -> False)."""
    return pd.Series(m).fillna(False).astype(bool)


def _blank(s):
    v = _text(s)
    return _mask(v.isna() | (v == '') | (v == 'nan'))


def _to_bool(s, name, what, blank=False):
    """Read True/False, 1/0, yes/no (any case); blanks become `blank`."""
    if s.dtype == bool:
        return s.astype(bool)
    v = _text(s)
    is_true, is_false = _mask(v.isin(_TRUE)), _mask(v.isin(_FALSE))
    bad = ~_blank(s) & ~is_true & ~is_false
    if bad.any():
        raise ScoreError(f'{what}: column {name} must be 1/0 or True/False, found: {_examples(s[bad])}')
    out = pd.Series(blank, index=s.index, dtype=bool)
    out[is_true] = True
    out[is_false] = False
    return out


def _to_float(s, name, what):
    num = pd.to_numeric(s, errors='coerce').astype(float)
    bad = _mask(num.isna()) & ~_blank(s)
    if bad.any():
        raise ScoreError(f'{what}: column {name} must be a number in decimal degrees or blank, found: {_examples(s[bad])}')
    return num


def _haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def score_tracks(sub, labels):
    """Score a submission against labels. Both arguments may be DataFrames or CSV paths.
    Returns a dict with a short 'summary' plus the details for tasks 2A, 2B and 2C."""
    S, L = _read(sub, 'submission'), _read(labels, 'labels')
    _require(S, SUB_COLUMNS, 'submission')
    _require(L, LABEL_COLUMNS, 'labels file')
    S, L = _clean_ids(S, 'submission'), _clean_ids(L, 'labels file')
    warnings = []

    # ---- validate and normalise the labels
    cat = _text(L['category'])
    bad = ~_mask(cat.isin(CATEGORIES))
    if bad.any():
        raise ScoreError(f'labels file has unknown categories: {_examples(L.category[bad].fillna("<blank>"))}')
    T = pd.DataFrame({'track_id': L.track_id, 'category': cat.astype(str)})
    for col in ('authorized', 'enters_alert_zone'):
        T[col] = _to_bool(L[col], col, 'labels file')
    if 'autonomous_no_rf' in L.columns:
        T['autonomous_no_rf'] = _to_bool(L['autonomous_no_rf'], 'autonomous_no_rf', 'labels file')
    else:
        T['autonomous_no_rf'] = False
        warnings.append('labels file has no autonomous_no_rf column: every drone with a known operator position is scored in 2C')
    for col in ('operator_lat', 'operator_lon'):
        T[col] = _to_float(L[col], col, 'labels file')

    # ---- validate and normalise the submission
    cat = _text(S['category'])
    blank = _blank(S['category'])
    if blank.any():
        raise ScoreError(f'submission has a blank category for {int(blank.sum())} track(s), e.g. {_examples(S.track_id[blank])}. '
                         f'Use one of: {", ".join(CATEGORIES)}')
    bad = ~_mask(cat.isin(CATEGORIES))
    if bad.any():
        raise ScoreError(f'submission has unknown categories: {_examples(S.category[bad])}. Use one of: {", ".join(CATEGORIES)}')
    P = pd.DataFrame({'track_id': S.track_id, 'category_pred': cat.astype(str)})
    no_alert = _blank(S['alert'])
    if no_alert.any():
        warnings.append(f'{int(no_alert.sum())} submission row(s) have a blank alert; scored as alert = 0')
    P['alert_pred'] = _to_bool(S['alert'], 'alert', 'submission', blank=False)
    for col, lim in (('operator_lat', 90), ('operator_lon', 180)):
        v = _to_float(S[col], col, 'submission')
        out = _mask(v.abs() > lim)
        if out.any():
            raise ScoreError(f'submission: {col} must be in decimal degrees (|value| <= {lim}), found: {_examples(v[out])}')
        P[col + '_pred'] = v
    half = P.operator_lat_pred.isna() ^ P.operator_lon_pred.isna()
    if half.any():
        warnings.append(f'{int(half.sum())} submission row(s) have only one of operator_lat/operator_lon; treated as blank')
        P.loc[half, ['operator_lat_pred', 'operator_lon_pred']] = np.nan

    # ---- join on the labelled tracks only
    n_extra = int((~P.track_id.isin(T.track_id)).sum())
    M = T.merge(P, on='track_id', how='left')
    missing = M.category_pred.isna()
    n_missing = int(missing.sum())
    if n_missing:
        warnings.append(f'{n_missing} labelled track(s) are missing from the submission, e.g. {_examples(M.track_id[missing])}; '
                        f'they count as wrong category, alert = 0 and {MISSING_ERROR_M:.0f} m')
    if n_extra:
        warnings.append(f'{n_extra} submission row(s) are not in the labels file and were ignored')

    # ---- 2A what is it
    y_true, y_pred = M.category.astype(str), M.category_pred.astype(object).where(~missing, 'missing').astype(str)
    per_class, f1 = {}, {}
    for c in CATEGORIES:
        tp = int(((y_pred == c) & (y_true == c)).sum())
        fp = int(((y_pred == c) & (y_true != c)).sum())
        fn = int(((y_pred != c) & (y_true == c)).sum())
        p, r, f1[c] = _prf(tp, fp, fn)
        per_class[c] = dict(precision=round(p, 4), recall=round(r, 4), f1=round(f1[c], 4), support=tp + fn, predicted=tp + fp)
    # classes with no true and no predicted tracks are left out of the average (as in scikit-learn)
    used = [c for c in CATEGORIES if per_class[c]['support'] or per_class[c]['predicted']]
    macro_f1 = float(np.mean([f1[c] for c in used])) if used else None
    cols = CATEGORIES + (['missing'] if n_missing else [])
    confusion = {t: {p: int(((y_true == t) & (y_pred == p)).sum()) for p in cols} for t in CATEGORIES}
    task_a = dict(macro_f1=None if macro_f1 is None else round(macro_f1, 4), accuracy=round(float((y_true == y_pred).mean()), 4) if len(M) else None,
                  classes_in_macro_average=used, per_class=per_class, confusion_matrix_rows_true_cols_predicted=confusion)

    # ---- 2B raise the alarm
    truth = ((y_true == 'drone').to_numpy(dtype=bool) & ~M.authorized.to_numpy(dtype=bool)
             & M.enters_alert_zone.to_numpy(dtype=bool))
    pred = _mask(M.alert_pred.where(~missing, False)).to_numpy(dtype=bool)
    tp, fp, fn = int((truth & pred).sum()), int((~truth & pred).sum()), int((truth & ~pred).sum())
    p, r, f = _prf(tp, fp, fn)
    task_b = dict(f1=round(f, 4), precision=round(p, 4), recall=round(r, 4), true_alerts=int(truth.sum()), predicted_alerts=int(pred.sum()),
                  true_positives=tp, false_positives=fp, missed=fn)
    if not truth.any() and not pred.any():
        task_b.update(f1=None, note='no true alerts and no predicted alerts in these tracks: F1 is undefined')

    # ---- 2C find the pilot
    elig = ((y_true == 'drone').to_numpy(dtype=bool) & ~M.autonomous_no_rf.to_numpy(dtype=bool)
            & M.operator_lat.notna().to_numpy() & M.operator_lon.notna().to_numpy())
    E = M[elig]
    has = E.operator_lat_pred.notna() & E.operator_lon_pred.notna()
    err = np.where(has, _haversine_m(E.operator_lat, E.operator_lon, E.operator_lat_pred.fillna(0), E.operator_lon_pred.fillna(0)), MISSING_ERROR_M)
    task_c = dict(median_error_m=round(float(np.median(err)), 1) if len(err) else None,
                  share_within_300m=round(float(np.mean(err <= WITHIN_M)), 4) if len(err) else None,
                  scored_tracks=int(len(err)), tracks_with_estimate=int(has.sum()),
                  median_error_m_where_estimated=round(float(np.median(err[has.to_numpy()])), 1) if has.any() else None)

    return dict(summary={'2A_macro_f1': task_a['macro_f1'], '2B_alert_f1': task_b['f1'], '2C_median_error_m': task_c['median_error_m']},
                tracks=dict(scored=int(len(M)), missing_from_submission=n_missing, extra_in_submission_ignored=n_extra),
                task_2A_category=task_a, task_2B_alert=task_b, task_2C_operator=task_c, warnings=warnings)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--submission', required=True, help='your CSV: track_id,category,alert,operator_lat,operator_lon')
    ap.add_argument('--labels', required=True, help='labels CSV (a validation cut of labels_train, or the test labels)')
    ap.add_argument('--out', help='also write the JSON result to this file')
    a = ap.parse_args(argv)
    try:
        res = score_tracks(a.submission, a.labels)
    except ScoreError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    for w in res['warnings']:
        print(f'warning: {w}', file=sys.stderr)
    text = json.dumps(res, indent=2)
    print(text)
    if a.out:
        with open(a.out, 'w') as fh:
            fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
