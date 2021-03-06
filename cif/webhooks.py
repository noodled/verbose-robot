# !/usr/bin/env python3

import ujson as json
import logging
import zmq
import multiprocessing
import os
import yaml
import requests
from pprint import pprint

from cif.constants import ROUTER_WEBHOOKS_ADDR

TRACE = os.getenv('CIF_WEBHOOK_TRACE', False)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if TRACE == '1':
    logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)


class Webhooks(multiprocessing.Process):

    def __init__(self):
        multiprocessing.Process.__init__(self)
        self.exit = multiprocessing.Event()

        if not os.path.exists('webhooks.yml'):
            logger.error('webhooks.yml file is missing...')
            return

        with open('webhooks.yml') as f:
            try:
                self.hooks = yaml.load(f)
            except yaml.YAMLError as exc:
                logger.error(exc)

    def terminate(self):
        self.exit.set()

    def stop(self):
        logger.info('shutting down')
        self.terminate()

    def is_search(self, data):
        if data.get('indicator') and data.get('limit') and data.get('nolog', '0') == '0':
            return True

        if not data.get('tags'):
            return

        if 'search' in set(data['tags']):
            return True

    def _to_slack(self, data):
        return {
            'text': "search: %s" % data.get('indicator')
        }

    def send(self, data):

        if len(self.hooks) == 0:
            logger.info('no webhooks to send to... is your webhooks.yml missing?')
            return

        if not self.is_search(data):
            return

        for h in self.hooks:
            if h == 'slack':
                data = self._to_slack(data)

            if isinstance(data, dict):
                data = json.dumps(data)

            resp = requests.post(self.hooks[h], data=data, headers={'Content-Type': 'application/json'}, timeout=5)
            logger.debug(resp.status_code)
            if resp.status_code not in [200, 201]:
                logger.error(resp.text)

    def start(self):
        context = zmq.Context()

        router = context.socket(zmq.PULL)
        router.connect(ROUTER_WEBHOOKS_ADDR)

        poller = zmq.Poller()
        poller.register(router, zmq.POLLIN)

        while not self.exit.is_set():
            try:
                s = dict(poller.poll(1000))
            except SystemExit or KeyboardInterrupt:
                break

            if router not in s:
                continue

            data = router.recv_multipart()
            logger.debug('got data..')
            logger.debug(data)

            self.send(json.loads(data[0]))

        router.close()
        context.term()
        del router
