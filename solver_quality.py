from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Tuple


EPS = 1e-12


def _sample_key(row: Dict[str, Any]) -> Tuple[float, float, float]:
    return (
        float(row.get('frequency_ghz', 0.0)),
        float(row.get('theta_inc_deg', row.get('theta_scat_deg', 0.0))),
        float(row.get('theta_scat_deg', 0.0)),
    )


def _display_db_from_linear(row: Dict[str, Any]) -> float:
    lin = float(row.get('rcs_linear', 0.0))
    if not math.isfinite(lin) or lin <= 0.0:
        lin = EPS
    return 10.0 * math.log10(lin)


def evaluate_mesh_convergence(
    base_result: Dict[str, Any],
    fine_result: Dict[str, Any],
    rms_limit_db: float,
    max_abs_limit_db: float,
) -> Dict[str, Any]:
    """Compare base and fine-mesh solves on common sample points."""

    base_rows = list(base_result.get('samples', []) or [])
    fine_rows = list(fine_result.get('samples', []) or [])
    fine_map = {_sample_key(row): row for row in fine_rows}

    deltas: List[float] = []
    missing = 0
    for row in base_rows:
        key = _sample_key(row)
        fine_row = fine_map.get(key)
        if fine_row is None:
            missing += 1
            continue
        deltas.append(_display_db_from_linear(row) - _display_db_from_linear(fine_row))

    if not deltas:
        return {
            'passed': False,
            'reason': 'no overlapping samples between base and fine mesh results',
            'sample_count': 0,
            'missing_count': int(missing),
            'rms_db': float('inf'),
            'max_abs_db': float('inf'),
            'limits': {
                'rms_limit_db': float(rms_limit_db),
                'max_abs_limit_db': float(max_abs_limit_db),
            },
        }

    rms = math.sqrt(sum(d * d for d in deltas) / len(deltas))
    max_abs = max(abs(d) for d in deltas)
    passed = math.isfinite(rms) and math.isfinite(max_abs) and rms <= rms_limit_db and max_abs <= max_abs_limit_db
    violations: List[str] = []
    if not math.isfinite(rms) or rms > rms_limit_db:
        violations.append(f'rms_db={rms:.6g} exceeds limit {float(rms_limit_db):.6g}')
    if not math.isfinite(max_abs) or max_abs > max_abs_limit_db:
        violations.append(f'max_abs_db={max_abs:.6g} exceeds limit {float(max_abs_limit_db):.6g}')
    if missing:
        violations.append(f'missing_count={int(missing)} sample(s) were absent from fine-mesh comparison')

    return {
        'passed': bool(passed),
        'reason': '; '.join(violations) if violations else 'mesh convergence passed',
        'sample_count': int(len(deltas)),
        'missing_count': int(missing),
        'rms_db': float(rms),
        'max_abs_db': float(max_abs),
        'limits': {
            'rms_limit_db': float(rms_limit_db),
            'max_abs_limit_db': float(max_abs_limit_db),
        },
    }



def scale_snapshot_panel_density(snapshot: Dict[str, Any], fine_factor: float) -> Dict[str, Any]:
    """Return a deep-copied geometry snapshot with denser panelization settings."""

    factor = float(fine_factor)
    if not math.isfinite(factor) or factor <= 1.0:
        raise ValueError('fine_factor must be a finite value > 1.0')

    out = copy.deepcopy(snapshot)
    for seg in out.get('segments', []) or []:
        props = list(seg.get('properties', []) or [])
        if len(props) < 2:
            props.extend([''] * (2 - len(props)))
        text = str(props[1]).strip()
        if not text:
            base_n = 1
        else:
            try:
                base_n = int(round(float(text)))
            except ValueError:
                base_n = 1

        if base_n > 0:
            new_n = max(base_n + 1, int(math.ceil(base_n * factor)))
        elif base_n < 0:
            new_mag = max(abs(base_n) + 1, int(math.ceil(abs(base_n) * factor)))
            new_n = -new_mag
        else:
            new_n = max(2, int(math.ceil(factor)))
        props[1] = str(new_n)
        seg['properties'] = props
    return out
