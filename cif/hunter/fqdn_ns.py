from dns.resolver import Timeout
import arrow

from csirtg_indicator import resolve_itype
from cifsdk.utils.network import resolve_ns
from csirtg_indicator import Indicator
import os
ENABLED = os.getenv('CIF_HUNTER_ADVANCED', False)


def process(i):
    return
    if not ENABLED:
        return

    if i.itype != 'fqdn':
        return

    if 'search' in i.tags:
        return

    try:
        r = resolve_ns(i.indicator)
        if not r:
            return
    except Timeout:
        return

    rv = []

    for rr in r:
        if str(rr).rstrip('.') in ["", 'localhost']:
            continue

        ip = Indicator(**i.__dict__())
        ip.probability = 0
        ip.indicator = str(rr)
        ip.lasttime = arrow.utcnow()

        try:
            resolve_itype(ip.indicator)
        except:
            continue

        ip.itype = 'ipv4'
        ip.rdata = i.indicator
        ip.confidence = 0
        rv.append(ip)

    return rv
