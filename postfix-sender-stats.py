#!/usr/bin/env python3
import argparse
import gzip
import re
import sys
from collections import defaultdict
from typing import Dict, List

# This script collects data from postfix log files to find out how many emails were send from a certain host


# Regex patterns for Postfix log lines
RE_CLIENT = re.compile(
    r'^(?P<ts>\w{3}\s+\d+\s[\d:]+)\s+\S+\s+postfix/smtpd\[\d+\]:\s+'
    r'(?P<qid>[A-F0-9]+):\s+client=(?P<host>[\w\.-]+)\[(?P<ip>[0-9a-fA-F\.:]+)\]'
)

RE_QMGR_FROM = re.compile(
    r'^.*postfix/qmgr\[\d+\]:\s+(?P<qid>[A-F0-9]+):\s+'
    r'from=<(?P<from>[^>]*)>,\s*size=(?P<size>\d+),\s*nrcpt=(?P<nrcpt>\d+)'
)

DELIVERY_AGENTS = r'(?:smtp|local|virtual|pipe|lmtp|error|relay)'
RE_DELIVERY = re.compile(
    rf'^.*postfix/{DELIVERY_AGENTS}\[\d+\]:\s+(?P<qid>[A-F0-9]+):\s+'
    r'(?:to=<(?P<to>[^>]*)>,\s+)?'
    r'(?:orig_to=<(?P<orig_to>[^>]*)>,\s+)?'
    r'relay=(?P<relay>[^,]+),.*?\sdsn=(?P<dsn>[0-9\.]+),\sstatus=(?P<status>\w+)'
)

# RE_REMOVED = re.compile(
#     r'^.*postfix/qmgr\[\d+\]:\s+(?P<qid>[A-F0-9]+):\s+removed'
# )

def open_maybe_gzip(path: str):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='replace')
    return open(path, 'rt', encoding='utf-8', errors='replace')

def parse_args():
    ap = argparse.ArgumentParser(
        description='Extract all recipients for messages received from a specific SMTP client host in Postfix logs.'
    )
    ap.add_argument('files', nargs='+', help='Log files to parse (supports .gz).')
    ap.add_argument('--host',
                    help='SMTP client hostname to match')
    ap.add_argument('--csv-header', action='store_true', help='Print CSV header.')
    ap.add_argument('--dsn-prefix', help='Only output rows with this dsn prefix (2. is success)')
    ap.add_argument('--invert-dsn-prefix', action='store_true',
                    help='Only output that do not start with --dsn-prefix.')
    ap.add_argument('--output-mode', choices=['csv', 'json'], default='csv')
    ap.add_argument("--output-cols", help='Choose output columns seperated by spaces, by default outputs everything',
                     choices=['timestamp','queue_id','client_host','client_ip','from','to','orig_to','relay','dsn','status','size'], nargs='+')
    ap.add_argument("--output-unique", help='Only output unique rows from the rows you selected',action='store_true')
    return ap.parse_args()

def main():
    args = parse_args()
    qids: Dict[str, Dict] = defaultdict(dict) # The queue ids connected to the host
    rows: List[Dict] = []

    def process_line(line: str):
        """
        Parse a single Postfix log line and extract information relevant to
        messages received from the target SMTP client host.

        This function matches the log line against several Postfix components:
          - **smtpd (client=...)**: Captures the queue ID, timestamp, client
            hostname, and client IP for messages received from the configured
            MX host. This initializes tracking for that queue ID.
          - **qmgr (from=...)**: Records the envelope sender, message size, and recipient count once the message enters the queue manager.
          - **delivery agents** one of smtp | local | virtual | pipe | lmtp/error | relay:
            Captures delivery attempts for tracked queue IDs, including final
            recipient (`to`), original recipient before aliasing (`orig_to`),
            relay target, DSN code, and delivery status. Each delivery attempt
            produces a new output row.

        Only messages associated with queue IDs previously seen from the target
        client host are tracked. Extracted rows are appended to the global
        `rows` list for later output.

        Args:
            line (str): A single line from a Postfix log file.
        """


        # Client accept line (smtpd)
        m = RE_CLIENT.match(line)
        if m and m.group('host') == args.host:
            # Collect the queue id for later
            qid = m.group('qid')
            qids[qid]['ts'] = m.group('ts')
            qids[qid]['client_host'] = m.group('host')
            qids[qid]['client_ip'] = m.group('ip')
            return

        # qmgr from=
        if m := RE_QMGR_FROM.match(line):
            qid = m.group('qid')
            if qid in qids:
                qids[qid]['from'] = m.group('from')
                qids[qid]['size'] = int(m.group('size'))
                qids[qid]['nrcpt'] = int(m.group('nrcpt'))
            return

        # delivery lines
        if m := RE_DELIVERY.match(line):
            qid = m.group('qid')
            if qid in qids:
                row = {
                    'timestamp': qids[qid].get('ts', ''),
                    'queue_id': qid,
                    'client_host': qids[qid].get('client_host', ''),
                    'client_ip': qids[qid].get('client_ip', ''),
                    'from': qids[qid].get('from', ''),
                    'to': m.group('to') or '',
                    'orig_to': m.group('orig_to') or '',
                    'relay': m.group('relay'),
                    'dsn': m.group('dsn'),
                    'status': m.group('status'),
                    'size': qids[qid].get('size', ''),
                }
                rows.append(row)
            return

        # removed
        # m = RE_REMOVED.match(line)
        # if m:
        #     return

    for path in args.files:
        try:
            with open_maybe_gzip(path) as fh:
                for line in fh:
                    process_line(line.rstrip('\n'))
        except Exception as e:
            print(f'# warning: error reading {path}: {e}', file=sys.stderr)

    # Filter rows
    if args.dsn_prefix:
        if args.invert_dsn_prefix:
            out_rows = [r for r in rows if not r['dsn'].startswith(args.dsn_prefix)]
        else:
            out_rows = [r for r in rows if r['dsn'].startswith(args.dsn_prefix)]
    else:
        out_rows = rows

    # Output columns
    args.output_cols = args.output_cols or ['timestamp','queue_id','client_host','client_ip','from','to','orig_to','relay','dsn','status','size']

    # filter only wanted keys
    out_rows = [{k: d[k] for k in args.output_cols if k in d} for d in out_rows]

    # unique filter
    if args.output_unique:
        unique_out = []
        seen = set()
        for row in out_rows:
            key = str(row)
            if key not in seen:
                seen.add(key)
                unique_out.append(row)
        out_rows = unique_out

    # Make the output
    if args.output_mode == 'csv':
        import csv
        csv_writer = csv.DictWriter(sys.stdout, fieldnames=args.output_cols)
        if args.csv_header: csv_writer.writeheader()
        csv_writer.writerows(out_rows)
    elif args.output_mode == 'json':
        import json
        json.dump(out_rows, sys.stdout)

if __name__ == '__main__':
    main()
