import asyncio
import importlib
import os
import sys

import pytest


@pytest.fixture(scope='module')
def gateway_main_module():
	patcher = pytest.MonkeyPatch()
	patcher.setattr(os, 'chdir', lambda *_args, **_kwargs: None)
	patcher.setattr(os, 'makedirs', lambda *_args, **_kwargs: None)

	import events

	class FakeEventProducer:
		def __init__(self, *args, **kwargs):
			self.started = False
			self.stopped = False
			self.published_events = []
		async def start(self):
			self.started = True
		async def stop(self):
			self.stopped = True
		async def publish(self, event):
			self.published_events.append(event)

	patcher.setattr(events, 'EventProducer', FakeEventProducer)

	try:
		sys.modules.pop('gateway.main', None)
		module = importlib.import_module('gateway.main')
	finally:
		patcher.undo()

	return module


def test_start_scan_endpoint_publishes_event_and_accepts_request(gateway_main_module):
	request = gateway_main_module.StartScanRequest(repository_url='https://github.com/acme/example.git')

	response = asyncio.run(gateway_main_module.start_scan_endpoint(request))

	assert response == {
		'status': 'accepted',
		'message': 'Scan process started for repository: https://github.com/acme/example.git',
		'repository_url': 'https://github.com/acme/example.git',
	}
	assert len(gateway_main_module.event_producer.published_events) == 1
	published_event = gateway_main_module.event_producer.published_events[0]
	assert published_event.repository_url == 'https://github.com/acme/example.git'
	assert published_event.key == 'https://github.com/acme/example.git'


def test_start_scan_endpoint_wraps_publish_failures(gateway_main_module, monkeypatch):
	async def fake_publish(event):
		raise RuntimeError('boom')

	monkeypatch.setattr(gateway_main_module.event_producer, 'publish', fake_publish)

	request = gateway_main_module.StartScanRequest(repository_url='https://github.com/acme/example.git')

	with pytest.raises(gateway_main_module.HTTPException, match='Failed to request scan: boom'):
		asyncio.run(gateway_main_module.start_scan_endpoint(request))


def test_lifespan_starts_and_stops_event_producer(gateway_main_module, monkeypatch):
	class FakeApp:
		pass

	async def run_lifespan():
		async with gateway_main_module.lifespan(FakeApp()):
			assert gateway_main_module.event_producer.started is True

	asyncio.run(run_lifespan())

	assert gateway_main_module.event_producer.stopped is True
