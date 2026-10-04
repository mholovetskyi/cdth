#!/usr/bin/env python3
"""Scorer for practice challenge 01 "Arctic Watch".

Task 1A - SAR detection classification
    Submission columns: detection_id,label
    label is one of: ais_vessel, dark_vessel, not_vessel
    Primary metric: macro F1 over the three classes. Every detection in the
    labels file is scored; a detection missing from the submission counts as
    wrong. Submission rows whose detection_id is not in the labels file are
    ignored.

Task 1B - behaviour events
    Submission columns: event_type,mmsi,start,end  (start/end in ISO 8601 UTC)
    mmsi may hold several values separated by ';' (e.g. "999000001;DARK").
    A predicted event matches a truth event of the same type when their MMSI
    sets intersect (DARK and blanks ignored) and their time intervals overlap
    once the prediction is padded by 2 hours on each side. Matching is
    one-to-one and greedy, largest overlap first.
    Primary metric: micro F1 over all events.
    Every truth event in the labels file is scored. Unmatched predictions are
    false positives only when their midpoint falls inside the scoring window
    (default: the hidden test window, 2025-09-10 to 2025-09-15 UTC), so
    predictions for days outside the window are ignored rather than punished.

Usage
    python score.py sar    --submission submissions/sar_labels.csv --labels my_val_sar_labels.csv
    python score.py events --submission submissions/behaviour_events.csv --labels my_val_events.csv \
        --window-start 2025-09-08T00:00:00Z --window-end 2025-09-10T00:00:00Z

Or from Python
    from score import score_sar, score_events
    result = score_sar("submissions/sar_labels.csv", "my_val_sar_labels.csv")

Only numpy, pandas and the standard library are needed.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

SAR_CLASSES = ["ais_vessel", "dark_vessel", "not_vessel"]
EVENT_TYPES = ["ais_gap_intentional", "protected_area_entry", "loitering", "rendezvous",
               "position_spoofing", "identity_change", "mmsi_clone"]
TEST_WINDOW_START = "2025-09-10T00:00:00Z"
TEST_WINDOW_END = "2025-09-15T00:00:00Z"
DEFAULT_SLACK_HOURS = 2.0


class ScoringInputError(ValueError):
    """Raised when a submission or labels file cannot be scored as given."""


# ---------------------------------------------------------------- helpers
def _load_table(obj, what):
    """Accept a DataFrame or a path to a CSV file; return a DataFrame of clean strings."""
    if isinstance(obj, pd.DataFrame):
        df = obj.copy()
    else:
        path = os.fspath(obj)
        if not os.path.exists(path):
            raise ScoringInputError(f"{what} file not found: {path}")
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except pd.errors.EmptyDataError:
            raise ScoringInputError(f"{what} file is empty: {path}")
    df.columns = [str(c).strip().lower() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].map(_clean_cell)
    return df.reset_index(drop=True)


def _clean_cell(v):
    if v is None:
        return ""
    if isinstance(v, float):
        if np.isnan(v):
            return ""
        if v.is_integer():
            return str(int(v))
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none", "<na>", "nat") else s


def _require_columns(df, cols, what):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ScoringInputError(
            f"{what} is missing required column(s): {', '.join(missing)}. "
            f"Expected columns: {','.join(cols)}. Found: {','.join(df.columns) or '(none)'}")


def _row_list(idx, limit=5):
    """Spreadsheet-style row numbers (header is line 1)."""
    rows = [str(int(i) + 2) for i in list(idx)[:limit]]
    more = len(idx) - limit
    return ", ".join(rows) + (f" (+{more} more)" if more > 0 else "")


def _safe_div(a, b):
    return float(a) / float(b) if b else None


def _f1(p, r):
    if p is None or r is None:
        return None
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def _r(x, nd=4):
    return None if x is None else round(float(x), nd)


# ---------------------------------------------------------------- task 1A
def _normalise_sar_labels(df, what):
    lab = df["label"].str.lower().str.replace("-", "_", regex=False).str.replace(" ", "_", regex=False)
    bad = ~lab.isin(SAR_CLASSES)
    if bad.any():
        examples = sorted(set(df.loc[bad, "label"]))[:5]
        raise ScoringInputError(
            f"{what} has {int(bad.sum())} row(s) with an unknown label {examples} "
            f"(csv rows {_row_list(np.flatnonzero(bad.values))}). Allowed labels: {', '.join(SAR_CLASSES)}")
    empty_id = df["detection_id"] == ""
    if empty_id.any():
        raise ScoringInputError(f"{what} has an empty detection_id in csv rows {_row_list(np.flatnonzero(empty_id.values))}")
    out = pd.DataFrame({"detection_id": df["detection_id"], "label": lab})
    dup = out.duplicated("detection_id", keep=False)
    warnings = []
    if dup.any():
        conflicting = out[dup].groupby("detection_id")["label"].nunique()
        conflicting = conflicting[conflicting > 1]
        if len(conflicting):
            raise ScoringInputError(
                f"{what} gives different labels for the same detection_id: "
                f"{', '.join(conflicting.index[:5])}{' ...' if len(conflicting) > 5 else ''}. Each detection must appear once.")
        n_extra = int(out.duplicated("detection_id").sum())
        warnings.append(f"{what}: dropped {n_extra} exact duplicate row(s)")
        out = out.drop_duplicates("detection_id")
    return out, warnings


def score_sar(sub_df_or_path, labels_df_or_path):
    """Score task 1A. Returns a dict (see module docstring)."""
    sub = _load_table(sub_df_or_path, "Submission")
    lab = _load_table(labels_df_or_path, "Labels")
    _require_columns(sub, ["detection_id", "label"], "Submission")
    _require_columns(lab, ["detection_id", "label"], "Labels file")
    sub, w1 = _normalise_sar_labels(sub, "Submission")
    lab, w2 = _normalise_sar_labels(lab, "Labels file")
    if len(lab) == 0:
        raise ScoringInputError("Labels file has no rows to score")

    merged = lab.merge(sub.rename(columns={"label": "pred"}), on="detection_id", how="left")
    merged["pred"] = merged["pred"].fillna("missing")
    n_missing = int((merged["pred"] == "missing").sum())
    n_ignored = int((~sub["detection_id"].isin(lab["detection_id"])).sum())

    cols = SAR_CLASSES + ["missing"]
    cm = pd.crosstab(merged["label"], merged["pred"]).reindex(index=SAR_CLASSES, columns=cols, fill_value=0)

    per_class, f1s = {}, []
    for c in SAR_CLASSES:
        tp = int(cm.loc[c, c])
        support = int(cm.loc[c].sum())
        predicted = int(cm[c].sum())
        p = _safe_div(tp, predicted) if predicted else (0.0 if support else None)
        r = _safe_div(tp, support)
        f = _f1(p, r) if support else (0.0 if predicted else None)
        per_class[c] = {"precision": _r(p), "recall": _r(r), "f1": _r(f), "support": support, "predicted": predicted}
        if f is not None:
            f1s.append(f)

    warnings = w1 + w2
    if n_missing:
        warnings.append(f"{n_missing} labelled detection(s) are missing from the submission and count as wrong")
    absent = [c for c in SAR_CLASSES if per_class[c]["f1"] is None]
    if absent:
        warnings.append(f"class(es) {absent} have no labelled and no predicted detections and are left out of the macro average")

    return {
        "task": "1A SAR detection classification",
        "primary_metric": "macro_f1",
        "macro_f1": _r(np.mean(f1s)) if f1s else None,
        "accuracy": _r((merged["label"] == merged["pred"]).mean()),
        "n_labelled": int(len(lab)),
        "n_submission_rows": int(len(sub)),
        "n_missing": n_missing,
        "n_ignored_not_in_labels": n_ignored,
        "per_class": per_class,
        "confusion_matrix": {
            "rows": "true label", "columns": "predicted label",
            "matrix": {c: {k: int(v) for k, v in cm.loc[c].items()} for c in SAR_CLASSES},
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------- task 1B
def _parse_times(series, what, col):
    # pandas >= 2 needs format="ISO8601" to accept mixed ISO strings; older pandas parses them per value
    kw = {"format": "ISO8601"} if int(pd.__version__.split(".")[0]) >= 2 else {}
    t = pd.to_datetime(series, utc=True, errors="coerce", **kw)
    bad = t.isna()
    if bad.any():
        examples = list(series[bad].head(3))
        raise ScoringInputError(
            f"{what}: could not read '{col}' as an ISO 8601 UTC time in csv rows {_row_list(np.flatnonzero(bad.values))} "
            f"(values {examples}). Use e.g. 2025-09-10T14:30:00Z")
    return t


def _iso(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value, name):
    try:
        t = pd.Timestamp(value)
    except (TypeError, ValueError):
        raise ScoringInputError(f"could not read {name} '{value}' as a time")
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _mmsi_set(text):
    out = set()
    for tok in str(text).split(";"):
        tok = tok.strip()
        if tok.endswith(".0") and tok[:-2].isdigit():
            tok = tok[:-2]
        if tok and tok.upper() != "DARK":
            out.add(tok)
    return frozenset(out)


def _prepare_events(df, what):
    _require_columns(df, ["event_type", "mmsi", "start", "end"], what)
    et = df["event_type"].str.lower().str.replace("-", "_", regex=False).str.replace(" ", "_", regex=False)
    bad = ~et.isin(EVENT_TYPES)
    if bad.any():
        examples = sorted(set(df.loc[bad, "event_type"]))[:5]
        raise ScoringInputError(
            f"{what} has {int(bad.sum())} row(s) with an unknown event_type {examples} "
            f"(csv rows {_row_list(np.flatnonzero(bad.values))}). Allowed types: {', '.join(EVENT_TYPES)}")
    start = _parse_times(df["start"], what, "start")
    end = _parse_times(df["end"], what, "end")
    backwards = end < start
    if backwards.any():
        raise ScoringInputError(f"{what}: 'end' is before 'start' in csv rows {_row_list(np.flatnonzero(backwards.values))}")
    out = pd.DataFrame({
        "event_type": et.values,
        "mmsi_raw": df["mmsi"].values,
        "mmsis": [_mmsi_set(m) for m in df["mmsi"]],
        "start": start.values,
        "end": end.values,
    })
    out["start"] = pd.to_datetime(out["start"], utc=True)
    out["end"] = pd.to_datetime(out["end"], utc=True)
    out["mid"] = out["start"] + (out["end"] - out["start"]) / 2
    if "event_id" in df.columns:
        out["event_id"] = df["event_id"].values
    else:
        out["event_id"] = [f"row{i + 2}" for i in range(len(df))]
    return out


def _greedy_match(pred, truth, slack):
    """One-to-one greedy matching, largest overlap first. Returns list of (pred_idx, truth_idx, overlap_hours)."""
    cands = []
    ps, pe, pm = pred["start"], pred["end"], pred["mid"]
    for j, t in truth.iterrows():
        same = (pred["event_type"] == t["event_type"]).values
        if not same.any():
            continue
        shares = np.array([bool(s & t["mmsis"]) for s in pred["mmsis"]]) & same
        if not shares.any():
            continue
        hits = shares & ((ps - slack) <= t["end"]).values & (t["start"] <= (pe + slack)).values
        for i in np.flatnonzero(hits):
            overlap = (min(pe.iat[i], t["end"]) - max(ps.iat[i], t["start"])).total_seconds() / 3600.0
            mid_gap = abs((pm.iat[i] - t["mid"]).total_seconds())
            cands.append((-overlap, mid_gap, int(i), int(j)))
    cands.sort()
    used_p, used_t, matches = set(), set(), []
    for neg_ov, _, i, j in cands:
        if i in used_p or j in used_t:
            continue
        used_p.add(i)
        used_t.add(j)
        matches.append((i, j, -neg_ov))
    return matches


def score_events(sub_df_or_path, labels_df_or_path, window_start=TEST_WINDOW_START,
                 window_end=TEST_WINDOW_END, slack_hours=DEFAULT_SLACK_HOURS, details=False):
    """Score task 1B. Returns a dict (see module docstring).

    window_start / window_end: the period the labels file covers. Unmatched
    predictions whose midpoint lies outside [window_start, window_end) are
    ignored. Defaults to the hidden test window.
    """
    sub = _load_table(sub_df_or_path, "Submission")
    lab = _load_table(labels_df_or_path, "Labels")
    pred = _prepare_events(sub, "Submission")
    truth = _prepare_events(lab, "Labels file")
    if len(truth) == 0:
        raise ScoringInputError("Labels file has no events to score")
    w0, w1 = _parse_utc(window_start, "window start"), _parse_utc(window_end, "window end")
    if w1 <= w0:
        raise ScoringInputError("window end must be after window start")
    outside = (truth["mid"] < w0) | (truth["mid"] >= w1)
    if outside.any():
        lo, hi = truth["mid"].min(), truth["mid"].max()
        raise ScoringInputError(
            f"{int(outside.sum())} labelled event(s) have their midpoint outside the scoring window "
            f"{_iso(w0)} to {_iso(w1)}. Pass the window your labels cover, e.g. "
            f"--window-start {_iso(lo.floor('D'))} --window-end {_iso(hi.floor('D') + pd.Timedelta(days=1))} "
            f"(in Python: window_start=..., window_end=...)")

    slack = pd.Timedelta(hours=float(slack_hours))
    matches = _greedy_match(pred, truth, slack) if len(pred) else []
    matched_p = {i for i, _, _ in matches}
    matched_t = {j for _, j, _ in matches}
    in_window = ((pred["mid"] >= w0) & (pred["mid"] < w1)).values if len(pred) else np.zeros(0, bool)
    scored_p = np.array([(i in matched_p) or bool(in_window[i]) for i in range(len(pred))], dtype=bool)
    fp_mask = scored_p & ~np.isin(np.arange(len(pred)), list(matched_p))

    tp, fp, fn = len(matches), int(fp_mask.sum()), len(truth) - len(matches)
    precision = _safe_div(tp, tp + fp) if (tp + fp) else 0.0
    recall = _safe_div(tp, tp + fn)
    per_type = {}
    for et in EVENT_TYPES:
        nt = int((truth["event_type"] == et).sum())
        tpt = sum(1 for _, j, _ in matches if truth["event_type"].iat[j] == et)
        fpt = int((fp_mask & (pred["event_type"] == et).values).sum()) if len(pred) else 0
        p = _safe_div(tpt, tpt + fpt) if (tpt + fpt) else None
        r = _safe_div(tpt, nt) if nt else None
        f = _f1(p if p is not None else 0.0, r) if nt else (0.0 if fpt else None)
        per_type[et] = {"n_truth": nt, "n_predicted": tpt + fpt, "tp": tpt, "fp": fpt, "fn": nt - tpt,
                        "precision": _r(p), "recall": _r(r), "f1": _r(f)}

    n_ignored = int((~scored_p).sum())
    warnings = []
    if n_ignored:
        warnings.append(f"{n_ignored} unmatched predicted event(s) have midpoints outside the scoring window and were ignored")
    result = {
        "task": "1B behaviour events",
        "primary_metric": "micro_f1",
        "micro_f1": _r(_f1(precision, recall)),
        "precision": _r(precision),
        "recall": _r(recall),
        "tp": tp, "fp": fp, "fn": fn,
        "n_truth_events": int(len(truth)),
        "n_submission_rows": int(len(pred)),
        "n_ignored_outside_window": n_ignored,
        "window": {"start": _iso(w0), "end": _iso(w1)},
        "slack_hours": float(slack_hours),
        "per_type": per_type,
        "warnings": warnings,
    }
    if details:
        result["matches"] = [{"submission_row": int(i) + 2, "truth_event": str(truth["event_id"].iat[j]),
                              "event_type": truth["event_type"].iat[j], "overlap_hours": round(ov, 2)}
                             for i, j, ov in sorted(matches)]
        result["unmatched_truth_events"] = [str(truth["event_id"].iat[j]) for j in range(len(truth)) if j not in matched_t]
        result["false_positive_rows"] = [int(i) + 2 for i in np.flatnonzero(fp_mask)]
    return result


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Score Arctic Watch submissions (task 1A 'sar' or task 1B 'events').")
    sp = ap.add_subparsers(dest="task")
    sp.required = True
    a = sp.add_parser("sar", help="Task 1A: SAR detection labels (columns detection_id,label)")
    a.add_argument("--submission", required=True, help="CSV with columns detection_id,label")
    a.add_argument("--labels", required=True, help="CSV with columns detection_id,label (e.g. a validation cut of labels_train)")
    b = sp.add_parser("events", help="Task 1B: behaviour events (columns event_type,mmsi,start,end)")
    b.add_argument("--submission", required=True, help="CSV with columns event_type,mmsi,start,end")
    b.add_argument("--labels", required=True, help="CSV with columns event_type,mmsi,start,end")
    b.add_argument("--window-start", default=TEST_WINDOW_START, help=f"start of the period the labels cover (default {TEST_WINDOW_START})")
    b.add_argument("--window-end", default=TEST_WINDOW_END, help=f"end of the period the labels cover (default {TEST_WINDOW_END})")
    b.add_argument("--slack-hours", type=float, default=DEFAULT_SLACK_HOURS, help="time slack on each side when matching (default 2)")
    b.add_argument("--details", action="store_true", help="also list matched / missed events")
    args = ap.parse_args(argv)
    try:
        if args.task == "sar":
            res = score_sar(args.submission, args.labels)
        else:
            res = score_events(args.submission, args.labels, args.window_start, args.window_end,
                               args.slack_hours, details=args.details)
    except ScoringInputError as e:
        print(f"score.py: error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
