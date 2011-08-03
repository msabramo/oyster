import datetime
from unittest import TestCase
from nose.tools import assert_raises
import pymongo
from oyster.client import Client


class ClientTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.client._wipe()


    def test_constructor(self):
        c = Client('127.0.0.1', 27017, 'testdb', mongo_log_maxsize=5000,
                   user_agent='test-ua', rpm=30, timeout=60,
                   retry_attempts=1, retry_wait_seconds=10)
        assert c.db.connection.host == '127.0.0.1'
        assert c.db.connection.port == 27017
        assert c.db.logs.options()['capped'] == True
        assert c.db.logs.options()['size'] == 5000
        assert c.scraper.user_agent == 'test-ua'
        assert c.scraper.requests_per_minute == 30
        assert c.scraper.timeout == 60
        assert c.scraper.retry_attempts == 1
        assert c.scraper.retry_wait_seconds == 10

    def test_log(self):
        self.client.log('action1', 'http://example.com')
        self.client.log('action2', 'http://test.com', error=True, pi=3)
        assert self.client.db.logs.count() == 2
        x = self.client.db.logs.find_one({'error': True})
        assert x['action'] == 'action2'
        assert x['url'] == 'http://test.com'
        assert x['pi'] == 3


    def test_track_url(self):
        # basic insert
        self.client.track_url('http://example.com', update_mins=30, pi=3)
        obj = self.client.db.tracked.find_one()
        assert '_random' in obj
        assert obj['update_mins'] == 30
        assert obj['metadata'] == {'pi': 3}

        # logging
        log = self.client.db.logs.find_one()
        assert log['action'] == 'track'
        assert log['url'] == 'http://example.com'

        # can't track same URL twice
        assert_raises(ValueError, self.client.track_url, 'http://example.com')

        # logged error
        assert self.client.db.logs.find_one({'error': 'already tracked'})


    def test_md5_versioning(self):
        doc = {'url': 'hello.txt'}
        self.client.fs.put('hello!', filename='hello.txt')
        assert not self.client.md5_versioning(doc, 'hello!')
        assert self.client.md5_versioning(doc, 'hey!')


    def test_update(self):
        self.client.track_url('http://google.com', update_mins=60)
        obj = self.client.db.tracked.find_one()
        self.client.update(obj)

        # check that metadata has been updated
        newobj = self.client.db.tracked.find_one()
        assert (newobj['last_update'] +
                datetime.timedelta(minutes=newobj['update_mins']) ==
                newobj['next_update'])
        assert newobj['consecutive_errors'] == 0
