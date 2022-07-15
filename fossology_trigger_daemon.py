# (c) Keiya Nobuta <nobuta.keiya@fujitsu.com>
# SPDX-License-Identifier: MIT

import sw360
import queue
import time
import threading
import sys


def _fossology_trigger(sw360_client, release_id, ProcessOutdated=False):
    url = sw360_client.url + 'resource/api/releases/' + release_id + '/triggerFossologyProcess'
    url = url + '?uploadDescription=uploadDescription'
    url = url + '&markFossologyProcessOutdated=' + str(ProcessOutdated).lower()
    resp = sw360_client.api_get(url)
    if resp:
        return resp.get('message')

    return None

def _fossology_check(sw360_client, release_id):
    url = sw360_client.url + 'resource/api/releases/' + release_id + '/checkFossologyProcessStatus'
    resp = sw360_client.api_get(url)
    if resp:
        return resp

def _trigger_worker(sw360_client, q, interval=10, retry=2):

    retry = retry + 1

    while True:
        release_id = q.get()

        trigger_done = False
        check_status = ''

        for i in range(retry):
            try:
                _fossology_trigger(sw360_client, release_id)
                trigger_done = True
                break
            except:
                time.sleep(interval)
                continue

        if trigger_done:
            for i in range(retry):
                try:
                    status = _fossology_check(sw360_client, release_id)
                    if status and 'fossologyProcessInfo' in status \
                       and 'externalTool' in status['fossologyProcessInfo'] \
                       and status['fossologyProcessInfo']['externalTool'] == 'FOSSOLOGY':
                        check_status = status['fossologyProcessInfo']['processStatus']
                        break
                except:
                    pass
                time.sleep(interval)

        if trigger_done:
            print('fossology process: release_id=' + release_id, 'triggered')
        if check_status:
            print('fossology check: release_id=' + release_id, check_status)
        if not trigger_done or not check_status:
            print('fossology process: release_id=' + release_id, 'ERROR', file=sys.stderr)

        q.task_done()

def fossology_trigger_daemon(sw360_client, releases=[], threads=2, interval=10):
    q = queue.Queue()
    for i in range(threads):
        threading.Thread(target=_trigger_worker,
                         args=(sw360_client, q, interval),
                         daemon=True).start()

    for release_id in releases:
        q.put(release_id)

    q.join()
