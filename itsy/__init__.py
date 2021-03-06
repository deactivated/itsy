import sys
from gevent import monkey
monkey.patch_all(thread=False)

import gevent
from gevent import Greenlet

import requests

from .client import Client
from .document import Document
from .queue import Queue, Empty


sentinel = object()


class Task(object):

    def __init__(self, url, document_type, referer=sentinel, interval=None,
                 high_priority=False):
        self.url = url
        self.document_type = document_type
        self.referer = referer
        self.interval = interval
        self.high_priority = high_priority
        self.scheduled_timestamp = 0


class Worker(Greenlet):

    def __init__(self, id, itsy):
        Greenlet.__init__(self)
        self.id = id
        self.itsy = itsy
        self.client = Client()

    def one(self):
        task = self.itsy.pop()
        print "%d: Handling task: [%s] %s" % (self.id,
                                              task.document_type,
                                              task.url)
        raw = self.client.get(url=task.url, referer=task.referer)

        handler = self.itsy.handlers[task.document_type]
        doc = Document(task, raw)
        result = handler(task, doc)
        if result:
            for new_task in result:
                print "  -> [%s] %s" % (new_task.document_type, new_task.url)
                if new_task.referer == sentinel:
                    new_task.referer = task.url
                self.itsy.push(new_task)

    def _run(self):
        while True:
            self.one()


class Itsy(object):

    def __init__(self):
        self.handlers = {}
        self.queue = Queue()

    def add_handler(self, document_type, func):
        assert document_type not in self.handlers
        self.handlers[document_type] = func

    def add_seed(self, url, document_type, referer=None, interval=None):
        self.push(Task(url=url, document_type=document_type,
                       referer=referer, interval=interval))

    def fetch(self, url, referer):
        r = requests.get(url)
        return r.text

    def pop(self):
        while True:
            try:
                return self.queue.pop()
            except Empty:
                print "TIMEOUT"

    def push(self, task):
        self.queue.push(task)

    def crawl(self, num_workers=5):
        workers = []
        for ii in range(num_workers):
            worker = Worker(ii, self)
            worker.start()
            workers.append(worker)
        gevent.joinall(workers)
