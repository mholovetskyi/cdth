#!/usr/bin/env python3
"""Ready and Resilient — scoring for the three tasks.

  python score.py forecast  --scenario scenario_practice --submission my_forecast.csv
  python score.py plan      --scenario scenario_practice --orders my_orders.csv --trips my_trips.csv [--details out.csv]
      orders.csv: community_id, order_time, destination_host_id[, share]   (share of the community's drivers sent to that host; default 1)
      trips.csv:  vehicle_id, depart_time, pickup_community_id, dropoff_host_id   (a vehicle's trips run in time order; ties keep file order)
      Evacuees delivered to a reception centre in a community the fire reaches are not safe: they count as exposed.
      score = 100*exposed + 100*trapped + 10*close_calls + 5*overflow + 1*unnecessary + 25*failed_trips   (lower is better)
        exposed: still in a community when the fire reaches it; trapped: caught on a road that closes while driving;
        close_calls: still in a community when the fire comes within 5 km (only if that happens after the decision time);
        overflow: arrivals beyond a host's capacity; unnecessary: people moved from places the fire never came within 15 km of.
  python score.py perimeter --scenario scenario_practice --submission my_perimeters.geojson

Truth is read from <scenario>/truth/ by default; organizers pass --truth <dir> for the eval scenario.
Needs: numpy, pandas, networkx, shapely. Times are ISO 8601 UTC strings (e.g. 2030-05-06T18:00:00Z).
"""
import argparse, heapq, json, math, os, sys
import numpy as np, pandas as pd, networkx as nx

HERE = os.path.dirname(os.path.abspath(__file__))
PERSONS_PER_VEHICLE = 2.5
BOARD_H, UNLOAD_H, AIR_OVERHEAD_H, AIR_GROUND_H = 20 / 60, 15 / 60, 0.4, 0.5
WEIGHTS = dict(exposed=100.0, trapped=100.0, close_calls=10.0, overflow=5.0, unnecessary=1.0, failed_trips=25.0)


def die(msg):
    sys.exit(f'ERROR: {msg}')


def hav(la1, lo1, la2, lo2):
    p1, p2 = np.radians(la1), np.radians(la2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


class World:
    def __init__(self, scenario, truth=None):
        sc = scenario if os.path.isabs(scenario) else os.path.join(HERE, scenario)
        if not os.path.isdir(sc):
            sc = scenario
        self.meta = json.load(open(os.path.join(sc, 'scenario.json')))
        self.truth = truth or os.path.join(sc, 'truth')
        if not os.path.isdir(self.truth):
            die(f'truth folder not found: {self.truth} (the eval truth is held by the organizers; pass --truth)')
        cm = os.path.join(os.path.dirname(os.path.abspath(sc)), 'common')
        self.t0 = pd.Timestamp(self.meta['t0'])
        self.TD, self.NH = float(self.meta['decision_hours_since_t0']), float(self.meta['hours'])
        self.C = pd.read_csv(os.path.join(cm, 'communities.csv'), dtype={'road_node_id': str}).set_index('community_id')
        self.H = pd.read_csv(os.path.join(cm, 'host_sites.csv'), dtype={'road_node_id': str}).set_index('host_id')
        self.F = pd.read_csv(os.path.join(cm, 'fleet.csv')).set_index('vehicle_id')
        self.A = pd.read_csv(os.path.join(cm, 'aerodromes.csv')).set_index('aerodrome_id')
        E = pd.read_csv(os.path.join(cm, 'road_edges.csv'))
        self.G = nx.Graph()
        for e in E.itertuples():
            if self.G.has_edge(e.u, e.v) and self.G[e.u][e.v]['tt'] <= e.travel_time_min / 60:
                continue
            self.G.add_edge(e.u, e.v, tt=e.travel_time_min / 60.0, eid=e.edge_id, cap=e.capacity_vph)
        self.CT = pd.read_csv(os.path.join(self.truth, 'community_fire_times.csv')).set_index('community_id')
        rc = pd.read_csv(os.path.join(self.truth, 'road_closures_truth.csv'))
        self.rclose = {r.edge_id: (r.closed_from_h, r.reopened_h if np.isfinite(r.reopened_h) else np.inf) for r in rc.itertuples()}
        ac = pd.read_csv(os.path.join(self.truth, 'aerodrome_closures_truth.csv'))
        self.aclose = {r.aerodrome_id: (r.closed_from_h, r.reopened_h if np.isfinite(r.reopened_h) else np.inf) for r in ac.itertuples()}
        self._pc = {}

    def h(self, iso):
        ts = pd.Timestamp(iso)
        if ts.tzinfo is None:
            ts = ts.tz_localize('UTC')
        return (ts - self.t0).total_seconds() / 3600.0

    def closed_set(self, t):
        return frozenset(e for e, (a, b) in self.rclose.items() if a <= t < b)

    def path(self, s, d, t):
        """Fastest path using only roads open at time t (closures already announced)."""
        cs = self.closed_set(t)
        key = (s, d, cs)
        if key not in self._pc:
            try:
                G = nx.subgraph_view(self.G, filter_edge=lambda u, v: self.G[u][v]['eid'] not in cs) if cs else self.G
                self._pc[key] = nx.dijkstra_path(G, s, d, weight='tt')
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                self._pc[key] = None
        return self._pc[key]

    def drive(self, s, d, t, slow=1.0):
        """Drive from node s to d starting at t. Reroutes at nodes when the next road is closed.
        Returns (arrival_time, status, first_edge_capacity) with status 'ok' | 'trapped' | 'no_route'."""
        if s == d:
            return t, 'ok', 4000
        p = self.path(s, d, t)
        if p is None:
            return t, 'no_route', 0
        cap0 = self.G[p[0]][p[1]]['cap']
        node, i = s, 0
        while node != d:
            nxt = p[i + 1]
            e = self.G[node][nxt]
            a, b = self.rclose.get(e['eid'], (np.inf, np.inf))
            if a <= t < b:                                   # closed when we get there: reroute from here
                p = self.path(node, d, t)
                if p is None:
                    return t, 'trapped', cap0
                i = 0
                continue
            t_out = t + e['tt'] * slow
            if t < a < t_out:                                # road closes (fire arrives) while we are on it
                return a, 'trapped', cap0
            t, node, i = t_out, nxt, i + 1
        return t, 'ok', cap0

    def air_ok(self, ad, t):
        a, b = self.aclose.get(ad, (np.inf, np.inf))
        return not (a <= t < b)

    def pick_aerodrome(self, lat, lon, veh, max_km=40.0):
        if veh.vehicle_type == 'helicopter_12':
            return None
        A = self.A
        ok = A.longest_runway_ft >= veh.min_runway_ft
        if bool(veh.needs_paved):
            ok &= A.paved.astype(bool)
        A = A[ok]
        d = hav(lat, lon, A.lat.values, A.lon.values)
        if not len(d) or d.min() > max_km:
            return False
        return A.index[int(np.argmin(d))]


# ------------------------------------------------------------------ task 4B: evacuation plan
def score_plan(W, orders_csv, trips_csv, details=None, quiet=False):
    warn = []
    O = pd.read_csv(orders_csv) if orders_csv else pd.DataFrame(columns=['community_id', 'order_time', 'destination_host_id'])
    T = pd.read_csv(trips_csv) if trips_csv else pd.DataFrame(columns=['vehicle_id', 'depart_time', 'pickup_community_id', 'dropoff_host_id'])
    for col in ['community_id', 'order_time', 'destination_host_id']:
        if col not in O.columns:
            die(f'orders file needs column {col}')
    for col in ['vehicle_id', 'depart_time', 'pickup_community_id', 'dropoff_host_id']:
        if col not in T.columns:
            die(f'trips file needs column {col}')
    C, H, F = W.C, W.H, W.F
    bad = set(O.community_id) - set(C.index) | set(T.pickup_community_id) - set(C.index)
    if bad:
        die(f'unknown community_id: {sorted(bad)[:5]}')
    bad = set(O.destination_host_id) - set(H.index) | set(T.dropoff_host_id) - set(H.index)
    if bad:
        die(f'unknown host_id: {sorted(bad)[:5]}')
    bad = set(T.vehicle_id) - set(F.index)
    if bad:
        die(f'unknown vehicle_id: {sorted(bad)[:5]}')
    if 'share' not in O.columns:
        O['share'] = 1.0
    O['share'] = O.share.fillna(1.0).astype(float)
    if (O.share < 0).any() or (O.groupby('community_id').share.sum() > 1 + 1e-6).any():
        die('order shares must be >= 0 and add up to at most 1 per community')
    O['t'] = [W.h(x) for x in O.order_time]; T['t'] = [W.h(x) for x in T.depart_time]
    if (O.t < W.TD - 1e-6).any() or (T.t < W.TD - 1e-6).any():
        warn.append('some times are before the decision time; they were moved to the decision time')
        O['t'] = O.t.clip(lower=W.TD); T['t'] = T.t.clip(lower=W.TD)

    ct = W.CT
    imp = {c: (ct.t_impact_h.get(c, np.nan)) for c in C.index}
    imp = {c: (v if np.isfinite(v) else np.inf) for c, v in imp.items()}
    near15 = {c: np.isfinite(ct.t_within_15km_h.get(c, np.nan)) for c in C.index}
    air_only = {c: C.loc[c, 'access'] == 'air_only' for c in C.index}
    # people still at home, by group
    self_left = {c: (0 if air_only[c] else int(C.loc[c, 'population'] - C.loc[c, 'needs_transport'])) for c in C.index}
    dep_left = {c: int(C.loc[c, 'population'] if air_only[c] else C.loc[c, 'needs_transport']) for c in C.index}
    events = []                                   # (time, kind, community, people)
    host_arr = {h: [] for h in H.index}           # arrivals: (time, people, origin community)
    trapped = {c: 0 for c in C.index}; moved = {c: 0 for c in C.index}
    failed = []
    dep_log = {c: [] for c in C.index}            # (time people left home, people)

    # --- private vehicles after an order: departures follow a response curve and share the community's exit (cordon) capacity
    S0 = dict(self_left)
    step = 0.25
    for c, rows in O.sort_values('t', kind='stable').groupby('community_id', sort=False):
        if air_only[c]:
            continue
        node = C.loc[c, 'road_node_id']
        cap_step = float(C.loc[c, 'exit_capacity_vph']) * PERSONS_PER_VEHICLE * step
        R_ = [dict(t0=r.t, S=S0[c] * r.share, q=0.0, rel=0.0, F=0.0, hn=H.loc[r.destination_host_id, 'road_node_id'], host=r.destination_host_id) for r in rows.itertuples()]
        t = min(r['t0'] for r in R_)
        stop = min(W.NH, imp[c])
        while t < stop and any(r['rel'] < r['S'] - 0.5 for r in R_):
            for r in R_:
                if t >= r['t0']:
                    Fc = 1 - math.exp(-(t + step - r['t0']) / 1.5)
                    r['q'] += r['S'] * (Fc - r['F']); r['F'] = Fc
            routes = {}
            for k, r in enumerate(R_):
                if r['q'] >= 0.5:
                    routes[k] = W.drive(node, r['hn'], t)
            live = {k: v for k, v in routes.items() if v[1] != 'no_route'}
            tq = sum(R_[k]['q'] for k in live)
            for k, (ta, st, _) in live.items():
                r = R_[k]
                rel = min(r['q'], cap_step * r['q'] / tq)
                r['q'] -= rel; r['rel'] += rel; self_left[c] -= rel
                r['last'] = (ta, st); dep_log[c].append((t, rel))
                if st == 'ok':
                    host_arr[r['host']].append((ta, rel, c)); moved[c] += rel
                else:
                    trapped[c] += rel
            t += step
        for r in R_:                                          # an order with under half a person left is done: they went with the last group
            rest = r['S'] - r['rel']
            if 0 < rest < 0.5 and 'last' in r:
                ta, st = r['last']
                r['rel'] += rest; self_left[c] -= rest; dep_log[c].append((t, rest))
                if st == 'ok':
                    host_arr[r['host']].append((ta, rest, c)); moved[c] += rest
                else:
                    trapped[c] += rest

    # --- buses and aircraft
    for vid, trips in T.sort_values('t', kind='stable').groupby('vehicle_id', sort=False):
        v = F.loc[vid]
        if v.vehicle_type == 'bus':
            loc = C.loc[v.base_community_id, 'road_node_id']
        else:
            loc = v.base_aerodrome_id
        avail = W.TD
        lost = False
        for tr in trips.itertuples():
            if lost:
                failed.append((vid, tr.pickup_community_id, 'vehicle lost earlier')); continue
            c = tr.pickup_community_id; hst = tr.dropoff_host_id
            t = max(tr.t, avail)
            if v.vehicle_type == 'bus':
                if air_only[c]:
                    failed.append((vid, c, 'no road access')); continue
                pn = C.loc[c, 'road_node_id']
                ta, st, _ = W.drive(loc, pn, t, slow=1.1)
                if st != 'ok':
                    failed.append((vid, c, f'en route to pickup: {st}'))
                    if st == 'trapped':
                        lost = True
                    continue
                if ta >= imp[c]:
                    failed.append((vid, c, 'arrived after the fire reached the community')); loc, avail = pn, ta; continue
                board = min(int(v.seats), dep_left[c]); dep_left[c] -= board
                tl = ta + BOARD_H
                hn = H.loc[hst, 'road_node_id']
                tb, st, _ = W.drive(pn, hn, tl, slow=1.1)
                if st == 'ok':
                    host_arr[hst].append((tb, board, c)); moved[c] += board; dep_log[c].append((tl, board))
                    loc, avail = hn, tb + UNLOAD_H
                else:
                    failed.append((vid, c, f'loaded, then {st}'))
                    lost = st == 'trapped'
                    if lost:
                        trapped[c] += board; dep_log[c].append((tl, board))
                    else:                                     # no open road to the host: passengers stay in the community
                        dep_left[c] += board
                        loc, avail = pn, tl
            else:
                lat, lon = C.loc[c, 'lat'], C.loc[c, 'lon']
                heli = v.vehicle_type == 'helicopter_12'
                pa = None if heli else W.pick_aerodrome(lat, lon, v)
                if pa is False:
                    failed.append((vid, c, 'no suitable aerodrome within 40 km')); continue
                hl = H.loc[hst]
                da = None if heli else W.pick_aerodrome(hl.lat, hl.lon, v)
                if da is False:
                    failed.append((vid, c, 'no suitable aerodrome near the host')); continue
                la0, lo0 = (W.A.loc[loc, 'lat'], W.A.loc[loc, 'lon']) if loc in W.A.index else (C.loc[loc, 'lat'], C.loc[loc, 'lon']) if loc in C.index else (H.loc[loc, 'lat'], H.loc[loc, 'lon'])
                la1, lo1 = (lat, lon) if heli else (W.A.loc[pa, 'lat'], W.A.loc[pa, 'lon'])
                la2, lo2 = (hl.lat, hl.lon) if heli else (W.A.loc[da, 'lat'], W.A.loc[da, 'lon'])
                f1 = hav(la0, lo0, la1, lo1) / v.cruise_kmh + (AIR_OVERHEAD_H if hav(la0, lo0, la1, lo1) > 1 else 0)
                ta = t + f1
                if not heli and not W.air_ok(pa, ta):
                    failed.append((vid, c, 'pickup aerodrome closed by fire')); continue
                if ta + AIR_GROUND_H >= imp[c]:
                    failed.append((vid, c, 'arrived after the fire reached the community')); continue
                board = min(int(v.seats), dep_left[c]); dep_left[c] -= board
                tl = ta + AIR_GROUND_H
                if not heli and not W.air_ok(pa, tl):
                    trapped[c] += board; failed.append((vid, c, 'aerodrome closed while loading')); continue
                tb = tl + hav(la1, lo1, la2, lo2) / v.cruise_kmh + AIR_OVERHEAD_H
                if not heli and not W.air_ok(da, tb):
                    failed.append((vid, c, 'destination aerodrome closed')); dep_left[c] += board; continue
                host_arr[hst].append((tb, board, c)); moved[c] += board; dep_log[c].append((tl, board))
                loc = hst if heli else da
                if heli:
                    loc = hl.community_id
                avail = tb + UNLOAD_H

    # --- evacuees delivered to a reception centre in a community the fire reaches are not safe there
    at_host = {c: 0.0 for c in C.index}
    unsafe = [h for h in H.index if np.isfinite(imp.get(H.loc[h, 'community_id'], np.inf))]
    for h in unsafe:
        for _, p, c in host_arr[h]:
            at_host[c] += p; moved[c] -= p
    n_unsafe = sum(at_host.values())
    if n_unsafe >= 0.5:
        used = [h for h in unsafe if host_arr[h]]
        warn.append(f'{n_unsafe:.0f} evacuees were sent to reception centres in communities the fire reaches ({", ".join(used)}); they count as exposed')

    # --- outcomes
    t5 = {c: ct.t_within_5km_h.get(c, np.nan) for c in C.index}
    close = {}
    for c in C.index:
        v = t5[c]
        if np.isfinite(v) and W.TD < v <= W.NH:
            gone = sum(p for tt_, p in dep_log[c] if tt_ <= v)
            close[c] = max(0.0, float(C.loc[c, 'population']) - gone)
        else:
            close[c] = 0.0
    rows = []
    for c in C.index:
        ex = at_host[c]
        if np.isfinite(imp[c]):
            ex += self_left[c] + dep_left[c]
        rows.append(dict(community_id=c, name=C.loc[c, 'name'], population=int(C.loc[c, 'population']), fire_impact_h=imp[c] if np.isfinite(imp[c]) else np.nan,
                         ordered=c in set(O.community_id), moved=round(moved[c]), trapped=round(trapped[c]), exposed=round(ex), close_calls=round(close[c]),
                         unnecessary=round(moved[c]) if not near15[c] else 0))
    R = pd.DataFrame(rows)
    overflow = 0.0
    for h, arr in host_arr.items():
        tot = sum(p for _, p, _ in arr)
        overflow += max(0.0, tot - H.loc[h, 'capacity_people'])
    res = dict(exposed=float(R.exposed.sum()), trapped=float(R.trapped.sum()), close_calls=float(R.close_calls.sum()), overflow=float(overflow),
               unnecessary=float(R.unnecessary.sum()), failed_trips=len(failed))
    res['score'] = sum(WEIGHTS[k] * res[k] for k in WEIGHTS)
    nothing = sum(WEIGHTS['exposed'] * (C.loc[c, 'population']) for c in C.index if np.isfinite(imp[c])) + \
        sum(WEIGHTS['close_calls'] * C.loc[c, 'population'] for c in C.index if np.isfinite(t5[c]) and W.TD < t5[c] <= W.NH)
    res['do_nothing_score'] = float(nothing)
    res['people_moved'] = float(R.moved.sum())
    if details:
        R.to_csv(details, index=False)
        pd.DataFrame(failed, columns=['vehicle_id', 'community_id', 'reason']).to_csv(os.path.splitext(details)[0] + '_failed_trips.csv', index=False)
    if not quiet:
        for w in warn:
            print('warning:', w)
        print(json.dumps({k: round(v, 1) if isinstance(v, float) else v for k, v in res.items()}, indent=2))
        hit = R[R.fire_impact_h.notna()]
        if len(hit):
            print('\ncommunities reached by fire:')
            print(hit[['community_id', 'name', 'population', 'fire_impact_h', 'ordered', 'moved', 'trapped', 'close_calls', 'exposed']].to_string(index=False))
    return res


# ------------------------------------------------------------------ task 4A: threat outlook
def score_forecast(W, sub_csv, quiet=False):
    S = pd.read_csv(sub_csv)
    need = ['community_id', 'p_24h', 'p_48h', 'p_72h']
    for c in need:
        if c not in S.columns:
            die(f'forecast file needs columns {need}')
    ct = W.CT.copy()
    t5 = ct.t_within_5km_h.fillna(np.inf)
    eligible = ct.index[t5 > W.TD]                         # already threatened at decision time -> not scored
    if S.community_id.duplicated().any():
        print('warning: duplicate community_id rows in the forecast; keeping the last one')
        S = S.drop_duplicates('community_id', keep='last')
    S = S.set_index('community_id').reindex(eligible)
    if S[['p_24h', 'p_48h', 'p_72h']].isna().any().any():
        n = int(S[['p_24h', 'p_48h', 'p_72h']].isna().any(axis=1).sum())
        print(f'warning: {n} communities missing from the submission were scored as p=0')
        S = S.fillna(0.0)
    out = {}
    for hh in (24, 48, 72):
        y = ((t5.loc[eligible] > W.TD) & (t5.loc[eligible] <= W.TD + hh)).astype(float).values
        p = np.clip(S[f'p_{hh}h'].values.astype(float), 0, 1)
        out[f'brier_{hh}h'] = float(np.mean((p - y) ** 2))
        out[f'positives_{hh}h'] = int(y.sum())
        clim = y.mean()
        out[f'brier_skill_{hh}h'] = float(1 - out[f'brier_{hh}h'] / max(np.mean((clim - y) ** 2), 1e-9)) if 0 < clim < 1 else float('nan')
    out['score_mean_brier'] = float(np.mean([out[f'brier_{h}h'] for h in (24, 48, 72)]))
    if not quiet:
        print(json.dumps(out, indent=2))
    return out


# ------------------------------------------------------------------ task 4C: perimeter nowcast
def score_perimeter(W, sub_geojson, quiet=False):
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from pyproj import Transformer
    from shapely.ops import transform as stf
    to = Transformer.from_crs(4326, 3978, always_xy=True)
    P = lambda gm: stf(lambda x, y, z=None: to.transform(x, y), gm)
    truth = json.load(open(os.path.join(W.truth, 'fire_perimeters_truth_3h.geojson')))
    tt = [f for f in truth['features'] if abs(f['properties']['hours_since_t0'] - W.TD) < 1e-6]
    sub = json.load(open(sub_geojson))
    out = {}
    for f in tt:
        fid = f['properties']['fire_id']
        gt = P(shape(f['geometry'])).buffer(0)
        ss = [P(shape(s['geometry'])).buffer(0) for s in sub['features'] if s['properties'].get('fire_id') == fid]
        if not ss:
            out[fid] = 0.0; continue
        pr = unary_union(ss)
        out[fid] = float(gt.intersection(pr).area / max(gt.union(pr).area, 1e-9))
    out['score_mean_iou'] = float(np.mean(list(out.values()))) if out else 0.0
    if not quiet:
        print(json.dumps({k: round(v, 3) for k, v in out.items()}, indent=2))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('task', choices=['plan', 'forecast', 'perimeter'])
    ap.add_argument('--scenario', default='scenario_practice')
    ap.add_argument('--truth', default=None)
    ap.add_argument('--orders'); ap.add_argument('--trips'); ap.add_argument('--submission'); ap.add_argument('--details')
    a = ap.parse_args()
    W = World(a.scenario, a.truth)
    if a.task == 'plan':
        score_plan(W, a.orders, a.trips, a.details)
    elif a.task == 'forecast':
        score_forecast(W, a.submission)
    else:
        score_perimeter(W, a.submission)
