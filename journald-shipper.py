#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@author David Lumaye
@licence CC Share-Alike https://creativecommons.org/licenses/by-nc-sa/4.0/

Part of this script is inspired by the work of George Notaras
His code (journald reader) has been adapted to my purposes.
"""

from systemd import journal
import datetime
import select
import pytz
import re
from elasticsearch import Elasticsearch
from daemon import runner


class JournaldShipper:
    def __init__(self):
        """Initialize Daemon."""
        self.stdin_path = '/dev/null'
        self.stdout_path = '/tmp/stdout'
        self.stderr_path = '/tmp/stderr'
        self.pidfile_path = '/var/run/journald-shipper.pid'
        self.pidfile_timeout = 1
        self.waitTime = 250
        self.localTimezone = 'CET'

    def run(self):
        print('--------------')
        print('Daemon Started')

        """
        Main loop.
        Used to seek events from Journald
        """
        # Create a systemd.journal.Reader instance
        j = journal.Reader()

        # Set the reader's default log level
        j.log_level(journal.LOG_DEBUG)

        # Only include entries since the current box has booted.
        j.this_boot()
        j.this_machine()

        # Move to the end of the journal
        j.seek_tail()

        # Important! - Discard old journal entries
        j.get_previous()

        # Create a poll object for journal entries
        p = select.poll()

        # Register the journal's file descriptor with the polling object.
        journal_fd = j.fileno()
        poll_event_mask = j.get_events()
        p.register(journal_fd, poll_event_mask)

        # Poll for new journal entries at regular interval
        while True:
            if p.poll(self.waitTime) is not None:
                if j.process() == journal.APPEND:
                    for entry in j:
                        self.insert_into_es(self.prepare_es_payload(entry))

    def key_cleaner(self, key):
        """
        Clean key to fit ES standards
        :param key: str
        :return: str
        """
        optimizedkey = key
        if key[0] == '_':
            optimizedkey = key[1:]
        return optimizedkey.lower()

    def check_key_allowance(self, key):
        """
        Check if key is allowed for data
        :param key: dict
        :return: bool
        """
        skippedkeys = {'_TRANSPORT', '_SOURCE_MONOTONIC_TIMESTAMP', '_SOURCE_REALTIME_TIMESTAMP', '_BOOT_ID',
                       '_MACHINE_ID'}
        if key in skippedkeys:
            return False
        if key[0:2] == '__':
            return False
        return True

    def prepare_es_payload(self, data):
        """
        Prepare payload for ES
        :param data: dict
        :return: dict
        """
        payload = dict()
        for key in data:
            if isinstance(data.get(key), (bytes, bytearray)):
                data[key] = data.get(key).decode()
            if not self.check_key_allowance(key):
                # Special check for timestamp
                if key == '__REALTIME_TIMESTAMP':
                    timestamp = data.get(key)
                    if not isinstance(timestamp, datetime.datetime):
                        timestamp = datetime.datetime.now()
                    payload['@timestamp'] = timestamp
                continue
            payload[self.key_cleaner(key)] = data.get(key)
        if payload.get('@timestamp') is None:
            payload['@timestamp'] = datetime.datetime.now()

        # Current timezone is local
        payload['@timestamp'] = payload['@timestamp'].astimezone(pytz.timezone(self.localTimezone))
        # Correct payload is UTC
        payload['@timestamp'] = payload['@timestamp'].astimezone(pytz.utc)
        payload['type'] = 'systemd'

        return self.split_payload(payload)

    def split_payload(self, data):
        """
        Split payload into sub-arguments
        :param data: dict
        :return: dict
        """
        if (data['message'] is None):
            return data

        sudo = r"\((?P<user>\S+)\)\sCMD\s\((?P<command>.*)\)"
        sudo_matches = re.finditer(sudo, data['message'])
        for match in sudo_matches:
            data['user'] = match.group('user')
            data['command'] = match.group('command')
            data['type'] = 'sudo'

        return data

    def insert_into_es(self, data):
        """
        Insert data into ElasicSearch
        :param data: dict
        :return:
        """
        timestamp = datetime.datetime.now()
        logstashIndex = 'logstash-' + timestamp.strftime("%Y.%m.%d")
        es = Elasticsearch()
        if not es.indices.exists(logstashIndex):
            es.indices.create(logstashIndex, ignore=400)
        es.index(index=logstashIndex, doc_type='doc', body=data)


if __name__ == '__main__':
    app = JournaldShipper()
    daemon_runner = runner.DaemonRunner(app)
    daemon_runner.do_action()
