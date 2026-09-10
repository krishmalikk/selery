"""Offline scorecard for manually captured chat answers. Makes no network/model calls."""
import argparse
import json
import math
import re
from pathlib import Path

REVIEW_FIELDS=('factual_support','correct_dates','missing_data_honesty','followup_continuity','motive_attribution')

def score(record):
    answer=record['answer']
    supplied=set(record['supplied_source_ids'])
    cited=re.findall(r'(?<!!)\[([^\]\n]+)\](?!\()',answer)
    unknown=sorted(set(cited)-supplied)
    supported=sum(source in supplied for source in cited)
    review=record.get('review',{})
    metrics={name:record.get(name) for name in ('latency_ms','first_text_ms','cost_usd')}
    for value in metrics.values():
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or value<0):
            raise ValueError('Measured latency/cost must be finite nonnegative values or null')
    reviewed=all(type(review.get(key)) is bool for key in REVIEW_FIELDS)
    return {'case':record['case'],'citation_mentions':len(cited),'recognized_citation_fraction':supported/len(cited) if cited else None,
        'unknown_source_ids':unknown,'metrics':metrics,'manual_review':{key:review.get(key) for key in REVIEW_FIELDS},
        'verdict':'pending_manual_review' if not reviewed else 'pass' if not unknown and all(review[key] for key in REVIEW_FIELDS) else 'fail',
        'limitation':'A recognized source ID does not establish factual support. Missing metrics remain unmeasured.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    records=json.loads(args.input.read_text())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps([score(record) for record in records],indent=2)+'\n')
    print(f'Wrote {len(records)} offline scorecards. No provider calls were made.')

if __name__=='__main__':main()
