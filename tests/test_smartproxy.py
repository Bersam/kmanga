# -*- coding: utf-8 -*-
#
# (c) 2016 Alberto Planas <aplanas@gmail.com>
#
# This file is part of KManga.
#
# KManga is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# KManga is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KManga.  If not, see <http://www.gnu.org/licenses/>.

import unittest

import mock

from scraper.middlewares import SmartProxy
from scraper.middlewares import RetryPartial


class Proxy(object):
    def __init__(self, proxy):
        self.proxy = proxy


class TestRetryPartial(unittest.TestCase):

    def setUp(self):
        error_codes = [500, 501]
        settings = mock.Mock(**{'getlist.return_value': error_codes})
        self.retry = RetryPartial(settings)

    def tearDown(self):
        self.retry = None

    def test_process_response(self):
        request_mock = mock.Mock()
        response_mock = mock.Mock()
        spider_mock = mock.Mock()

        response_mock.flags = []
        response_mock.status = 200

        self.retry.process_response(request_mock, response_mock, spider_mock)
        self.assertEqual(response_mock.status, 200)

    def test_process_response_partial(self):
        request_mock = mock.Mock()
        response_mock = mock.Mock()
        spider_mock = mock.Mock()

        response_mock.flags = ['partial']
        response_mock.status = 200

        self.retry.process_response(request_mock, response_mock, spider_mock)
        self.assertEqual(response_mock.status, 500)

    def test_process_response_partial_error(self):
        request_mock = mock.Mock()
        response_mock = mock.Mock()
        spider_mock = mock.Mock()

        response_mock.flags = ['partial']
        response_mock.status = 501

        self.retry.process_response(request_mock, response_mock, spider_mock)
        self.assertEqual(response_mock.status, 501)


class TestSmartProxy(unittest.TestCase):

    def setUp(self):
        error_codes = [[500], [301]]
        settings = mock.Mock(**{'getlist.side_effect': error_codes})
        self.proxy = SmartProxy(settings)

    def tearDown(self):
        self.proxy = None

    @mock.patch('scraper.middlewares.needs_proxy')
    def test_process_request_skip(self, needs_proxy):
        request_mock = mock.Mock()
        spider_mock = mock.Mock()
        self.proxy.process_request(request_mock, spider_mock)
        needs_proxy.assert_not_called()

        spider_mock._operation = 'no-manga'
        self.proxy.process_request(request_mock, spider_mock)
        needs_proxy.assert_not_called()

        request_mock.meta = {'proxy': 'proxy'}
        spider_mock._operation = 'manga'
        self.proxy.process_request(request_mock, spider_mock)
        needs_proxy.assert_not_called()

    @mock.patch('scraper.middlewares.needs_proxy')
    def test_process_request_skip2(self, needs_proxy):
        request_mock = mock.Mock()
        spider_mock = mock.Mock()

        request_mock.meta = {}
        spider_mock._operation = 'manga'
        spider_mock.name = 'spider'
        needs_proxy.return_value = False
        self.proxy.process_request(request_mock, spider_mock)
        needs_proxy.assert_called_once_with('spider')

    @mock.patch('scraper.middlewares.Proxy')
    @mock.patch('scraper.middlewares.needs_proxy')
    def test_process_request_proxy(self, needs_proxy, proxy):
        request_mock = mock.Mock()
        spider_mock = mock.Mock()

        request_mock.meta = {}
        spider_mock._operation = 'manga'
        spider_mock.name = 'spider'
        needs_proxy.return_value = True

        order_by = mock.Mock(**{'first.return_value': Proxy('myproxy')})
        filter_ = mock.Mock(**{'order_by.return_value': order_by})
        proxy.objects = mock.Mock(**{'filter.return_value': filter_})

        self.proxy.process_request(request_mock, spider_mock)

        self.assertTrue('proxy' in request_mock.meta)
        self.assertEqual(request_mock.meta['proxy'], 'http://myproxy')

    @mock.patch('scraper.middlewares.Proxy')
    @mock.patch('scraper.middlewares.needs_proxy')
    def test_process_request_no_proxy(self, needs_proxy, proxy):
        request_mock = mock.Mock()
        spider_mock = mock.Mock()

        request_mock.meta = {}
        spider_mock._operation = 'manga'
        spider_mock.name = 'spider'
        needs_proxy.return_value = True

        order_by = mock.Mock(**{'first.return_value': None})
        filter_ = mock.Mock(**{'order_by.return_value': order_by})
        proxy.objects = mock.Mock(**{'filter.return_value': filter_})

        self.proxy.process_request(request_mock, spider_mock)

        self.assertTrue('proxy' not in request_mock.meta)

    def test_process_response_skip(self):
        request_mock = mock.Mock()
        response_mock = mock.Mock()
        spider_mock = mock.Mock()
        request_mock.meta = {}

        self.proxy._delete_proxy_from_request = mock.Mock()
        self.proxy._valid_redirect = mock.Mock()

        self.proxy.process_response(request_mock, response_mock, spider_mock)

        self.proxy._delete_proxy_from_request.assert_not_called()
        self.proxy._valid_redirect.assert_not_called()

    def test_process_response_skip2(self):
        request_mock = mock.Mock()
        response_mock = mock.Mock()
        spider_mock = mock.Mock()
        request_mock.meta = {'proxy': 'proxy'}

        self.proxy._delete_proxy_from_request = mock.Mock()
        self.proxy._valid_redirect = mock.Mock()

        self.proxy.process_response(request_mock, response_mock, spider_mock)

        self.proxy._delete_proxy_from_request.assert_not_called()
        self.proxy._valid_redirect.assert_not_called()

    def test_process_response_retry(self):
        request_mock = mock.Mock()
        response_mock = mock.Mock()
        spider_mock = mock.Mock()
        request_mock.meta = {'proxy': 'proxy'}
        response_mock.status = 301

        self.proxy._delete_proxy_from_request = mock.Mock()
        self.proxy._valid_redirect = mock.Mock()

        self.proxy.process_response(request_mock, response_mock, spider_mock)

        self.proxy._delete_proxy_from_request.assert_called_with(
            request_mock, spider_mock)
        self.proxy._valid_redirect.assert_not_called()

    def test_process_response_error_no_valid(self):
        request_mock = mock.Mock()
        response_mock = mock.Mock()
        spider_mock = mock.Mock()
        request_mock.meta = {'proxy': 'proxy'}
        request_mock.url = 'url'
        response_mock.status = 500
        response_mock.headers = {}

        self.proxy._delete_proxy_from_request = mock.Mock()
        self.proxy._valid_redirect = mock.Mock(return_value=False)
        self.proxy._map_status_error = mock.Mock()

        self.proxy.process_response(request_mock, response_mock, spider_mock)

        self.proxy._delete_proxy_from_request.assert_called_with(
            request_mock, spider_mock)
        self.proxy._valid_redirect.assert_called_with(500, 'url', None)
        self.proxy._map_status_error.assert_called_with(response_mock)

    def test_process_response_error_valid_not_redirect(self):
        request_mock = mock.Mock()
        response_mock = mock.Mock()
        spider_mock = mock.Mock()
        request_mock.meta = {'proxy': 'proxy'}
        request_mock.url = 'url'
        response_mock.status = 500
        response_mock.headers = {}

        self.proxy._delete_proxy_from_request = mock.Mock()
        self.proxy._valid_redirect = mock.Mock(return_value=True)

        self.proxy.process_response(request_mock, response_mock, spider_mock)

        self.proxy._delete_proxy_from_request.assert_not_called()
        self.proxy._valid_redirect.assert_called_with(500, 'url', None)

    def test_process_response_error_valid_redirect(self):
        request_mock = mock.Mock()
        response_mock = mock.Mock()
        spider_mock = mock.Mock()
        request_mock.meta = {'proxy': 'proxy', 'dont_redirect': True}
        request_mock.url = 'url'
        response_mock.status = 500
        response_mock.headers = {}

        self.proxy._delete_proxy_from_request = mock.Mock()
        self.proxy._valid_redirect = mock.Mock(return_value=True)

        self.proxy.process_response(request_mock, response_mock, spider_mock)

        self.proxy._delete_proxy_from_request.assert_not_called()
        self.proxy._valid_redirect.assert_called_with(500, 'url', None)
        self.assertFalse('dont_redirect' in request_mock.meta)

    def test_process_exception_skip(self):
        request_mock = mock.Mock()
        spider_mock = mock.Mock()
        request_mock.meta = {}
        self.proxy.process_exception(request_mock, None, spider_mock)

    @mock.patch('scraper.middlewares.Proxy')
    def test_process_exception(self, proxy):
        request_mock = mock.Mock()
        spider_mock = mock.Mock()
        request_mock.meta = {'proxy': 'http://myproxy'}
        self.proxy.process_exception(request_mock, None, spider_mock)

        self.assertTrue('proxy' not in request_mock.meta)

    @mock.patch('scraper.middlewares.Proxy')
    def test_process_exception_error(self, proxy):
        request_mock = mock.Mock()
        spider_mock = mock.Mock()
        request_mock.meta = {'proxy': 'http://myproxy'}

        proxy.DoesNotExist = Exception
        proxy.objects = mock.Mock(**{'get.side_effect': proxy.DoesNotExist()})
        self.proxy.process_exception(request_mock, None, spider_mock)

        self.assertTrue('proxy' not in request_mock.meta)

    def test_map_status_error(self):
        response_mock = mock.Mock()
        response_mock.status = 200
        response_mock.headers = {}
        self.proxy._map_status_error(response_mock)
        self.assertEqual(response_mock.status, 500)

        response_mock.status = 200
        response_mock.headers = {'Content-Encoding': 'content-encoding'}
        self.proxy._map_status_error(response_mock)
        self.assertEqual(response_mock.status, 500)
        self.assertFalse('Content-Encoding' in response_mock.headers)

    def test_valid_redirect(self):
        status = 200
        url_from = None
        url_to = None
        self.assertFalse(self.proxy._valid_redirect(status, url_from, url_to))

        status = 302
        url_from = 'http://mangahere.com/manga1'
        url_to = '10.0.0.1'
        self.assertFalse(self.proxy._valid_redirect(status, url_from, url_to))

        status = 302
        url_from = 'http://mangahere.com/manga1'
        url_to = 'http://mangahere.com/manga1'
        self.assertFalse(self.proxy._valid_redirect(status, url_from, url_to))

        status = 302
        url_from = 'http://mangahere.com/manga1.html'
        url_to = 'http://mangahere.com/new/manga1.html'
        self.assertTrue(self.proxy._valid_redirect(status, url_from, url_to))
