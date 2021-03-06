
from cifsdk.utils.network import resolve_ns
import logging
import os
import re

ENABLE_PEERS = os.environ.get('CIF_GATHERERS_PEERS_ENABLED')


def _resolve(data):
    return resolve_ns('{}.{}'.format(data, 'peer.asn.cymru.com', timeout=15), t='TXT')


def process(indicator):
    if ENABLE_PEERS:
        return indicator

    if indicator.is_private() or not indicator.itype == 'ipv4':
        return indicator

    i = str(indicator.indicator)
    match = re.search('^(\S+)\/\d+$', i)
    if match:
        i = match.group(1)

    # cache it to the /24
    i = list(reversed(i.split('.')))
    i = '0.{}.{}.{}'.format(i[1], i[2], i[3])

    answers = _resolve(i)
    if answers is None or len(answers) == 0:
        return

    if not indicator.peers:
        indicator.peers = []

    # Separate fields and order by netmask length
    # 23028 | 216.90.108.0/24 | US | arin | 1998-09-25
    # 701 1239 3549 3561 7132 | 216.90.108.0/24 | US | arin | 1998-09-25
    for p in answers:
        bits = str(p).replace('"', '').strip().split(' | ')
        asn = bits[0]
        prefix = bits[1]
        cc = bits[2]
        rir = bits[3]
        asns = asn.split(' ')
        for a in asns:
            indicator.peers.append({
                'asn': a,
                'prefix': prefix,
                'cc': cc,
                'rir': rir
            })

    return indicator
