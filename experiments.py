#!/usr/bin/env python3
"""CMU IronViz: standardized telemetry + four allocation experiments.

Requires: pandas, numpy. Optional: numba (accelerates event simulation).

Pricing CSV MUST have columns: model,input_per_million,cached_input_per_million,output_per_million.
Prices are USD per 1 million tokens; use documented, model-specific rates.

Example:
 python ironviz_experiments.py --openai 'openai_pipeline_telemetry_raw(1).csv' \
   --gemini 'gemini_pipeline_telemetry_raw(1).csv' --prices prices.csv --out results
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

try:
    from numba import njit
except ImportError:
    def njit(*args, **kwargs):
        def deco(f): return f
        return deco

MODELS = ('gpt-4o', 'gpt-4o-mini', 'o1-preview', 'gemini-1.5-pro', 'gemini-1.5-flash')
TENANT_SHOCK_DEFAULT = 'org-engineering-dev'
BUDGET_LEVELS = (1.00, .85, .70, .50)
POLICIES = ('fcfs', 'fixed_quota', 'adaptive', 'smart_routing')


def _parse_usage(series, provider):
    vals = []
    for raw in series:
        if pd.isna(raw) or raw == '':
            vals.append((np.nan, np.nan, np.nan))
            continue
        try:
            d = json.loads(raw)
            if provider == 'openai':
                vals.append((d.get('prompt_tokens'), d.get('completion_tokens'),
                             (d.get('prompt_tokens_details') or {}).get('cached_tokens', 0)))
            else:
                vals.append((d.get('promptTokenCount'), d.get('candidatesTokenCount'),
                             d.get('cachedContentTokenCount', 0)))
        except (TypeError, ValueError, AttributeError):
            vals.append((np.nan, np.nan, np.nan))
    return pd.DataFrame(vals, columns=['input_tokens', 'output_tokens', 'cached_tokens'])


def clean_telemetry(openai_path, gemini_path):
    chunks = []
    mappings = [
        (openai_path, 'openai', {'id':'request_id', 'created_at':'timestamp',
         'model':'model', 'organization_id':'tenant', 'status_code':'status', 'error':'error'}, 'usage'),
        (gemini_path, 'gemini', {'response_id':'request_id', 'timestamp':'timestamp',
         'model_version':'model', 'gcp_project_id':'tenant', 'http_response_code':'status',
         'error_details':'error'}, 'usageMetadata'),
    ]
    for path, provider, renames, usage_col in mappings:
        raw = pd.read_csv(path, dtype={usage_col:'string'})
        usage = _parse_usage(raw[usage_col], provider)
        frame = raw.rename(columns=renames)[list(renames.values())].reset_index(drop=True)
        frame = pd.concat([frame, usage], axis=1)
        frame['provider'] = provider
        chunks.append(frame)
    df = pd.concat(chunks, ignore_index=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
    df['status'] = pd.to_numeric(df['status'], errors='coerce')
    df['success'] = df['status'].between(200, 299)
    for col in ('input_tokens','output_tokens','cached_tokens'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['total_tokens'] = df['input_tokens'] + df['output_tokens']
    df['uncached_tokens'] = df['input_tokens'] - df['cached_tokens']
    bad = df['timestamp'].isna() | df['request_id'].isna() | df['tenant'].isna() | df['model'].isna()
    bad |= df['request_id'].duplicated(keep=False)
    for col in ('input_tokens','output_tokens','cached_tokens','uncached_tokens'):
        bad |= df['success'] & (df[col].isna() | (df[col] < 0))
    if bad.any():
        raise ValueError(f'{bad.sum()} invalid/duplicate records; inspect input data')
    return df.sort_values(['timestamp','request_id'], kind='stable').reset_index(drop=True)


def read_prices(path):
    p = pd.read_csv(path)
    required = {'model','input_per_million','cached_input_per_million','output_per_million'}
    if not required.issubset(p.columns):
        raise ValueError(f'Pricing CSV missing columns: {sorted(required-set(p.columns))}')
    if p.model.duplicated().any():
        raise ValueError('Pricing CSV has duplicate model entries')
    for c in required - {'model'}:
        p[c] = pd.to_numeric(p[c], errors='raise')
        if p[c].isna().any() or (p[c] < 0).any():
            raise ValueError(f'Missing or negative prices in {c}; fill every price cell')
    missing = set(MODELS) - set(p.model)
    if missing: raise ValueError(f'Missing prices for {sorted(missing)}')