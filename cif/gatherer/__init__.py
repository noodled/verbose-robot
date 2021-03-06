#!/usr/bin/env python3

import ujson as json
import logging
import traceback
import zmq
import multiprocessing
import os
from pprint import pprint

from csirtg_indicator import Indicator
from cif.constants import GATHERER_ADDR, GATHERER_SINK_ADDR
from cifsdk.msg import Msg
from cifsdk.utils import load_plugins
import cif.gatherer


SNDTIMEO = 30000
LINGER = 0
TRACE = os.environ.get('CIF_GATHERER_TRACE')

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

if TRACE:
    logger.setLevel(logging.DEBUG)


class Gatherer(multiprocessing.Process):
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        return self

    def __init__(self, pull=GATHERER_ADDR, push=GATHERER_SINK_ADDR):
        multiprocessing.Process.__init__(self)
        self.pull = pull
        self.push = push
        self.exit = multiprocessing.Event()

        self.gatherers = load_plugins(cif.gatherer.__path__)

    def terminate(self):
        self.exit.set()

    def process(self, data):
        if isinstance(data, dict):
            data = [data]

        indicators = [Indicator(**d) for d in data]
        for g in self.gatherers:
            for i in indicators:
                try:
                    g.process(i)
                except Exception as e:
                    from pprint import pprint
                    pprint(i)

                    logger.error('gatherer failed: %s' % g)
                    logger.error(e)
                    traceback.print_exc()

        return [i.__dict__() for i in indicators]

    def start(self):
        context = zmq.Context()
        pull_s = context.socket(zmq.PULL)
        push_s = context.socket(zmq.PUSH)

        push_s.SNDTIMEO = SNDTIMEO
        push_s.setsockopt(zmq.LINGER, 3)
        pull_s.setsockopt(zmq.LINGER, 3)

        pull_s.connect(self.pull)
        push_s.connect(self.push)

        logger.info('connected')

        poller = zmq.Poller()
        poller.register(pull_s)

        while not self.exit.is_set():
            try:
                s = dict(poller.poll(1000))
            except KeyboardInterrupt or SystemExit:
                break

            if pull_s not in s:
                continue

            id, token, mtype, data = Msg().recv(pull_s)

            data = json.loads(data)

            data = self.process(data)
            Msg(id=id, mtype=mtype, token=token, data=data).send(push_s)

        # pull_s.close()
        # push_s.close()
        # context.term()


def main():
    g = Gatherer()

    data = {"indicator": "example.com"}
    data = g.process(data)
    pprint(data)


if __name__ == '__main__':
    main()
