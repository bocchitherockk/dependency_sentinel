import asyncio
import importlib
import os
import sys
from types import SimpleNamespace

import pytest

from common.schemas.ManifestFile import ManifestFile


@pytest.fixture(scope='module')
def scanner_main_module():
	patcher = pytest.MonkeyPatch()
	patcher.setattr(os, 'chdir', lambda *_args, **_kwargs: None)
	patcher.setattr(os, 'makedirs', lambda *_args, **_kwargs: None)

	import events

	class FakeEventProducer:
		def __init__(self, *args, **kwargs):
			self.published_events = []
		async def start(self):
			return None
		async def stop(self):
			return None
		async def publish(self, event):
			self.published_events.append(event)

	class FakeEventConsumer:
		def __init__(self, *args, **kwargs):
			self.callback = None
		async def start(self):
			return None
		async def stop(self):
			return None
		async def consume(self, callback):
			self.callback = callback

	patcher.setattr(events, 'EventProducer', FakeEventProducer)
	patcher.setattr(events, 'EventConsumer', FakeEventConsumer)

	try:
		sys.modules.pop('repository_scanner_service.main', None)
		module = importlib.import_module('repository_scanner_service.main')
	finally:
		patcher.undo()

	return module


def test_handle_topic_repository_cloned_publishes_scanned_event(scanner_main_module, monkeypatch):
	scanned_manifests = [
		ManifestFile(path='package.json', dependencies=[], dev_dependencies=[])
	]
	published_events = []

	async def fake_scan_repository(repository_name):
		assert repository_name == 'example'
		return scanned_manifests

	async def fake_publish(event):
		published_events.append(event)

	monkeypatch.setattr(scanner_main_module, 'scan_repository', fake_scan_repository)
	monkeypatch.setattr(
		scanner_main_module,
		'event_producer',
		SimpleNamespace(publish=fake_publish),
	)

	asyncio.run(
		scanner_main_module.handle_topic_repository_cloned(
			key='example',
			value={'repository_name': 'example'},
			msg=None,
		)
	)

	assert len(published_events) == 1
	assert published_events[0].repository_name == 'example'
	assert published_events[0].key == 'example'
	assert published_events[0].detected_manifest_files == scanned_manifests


def test_handle_topic_repository_cloned_rejects_empty_repository_name(scanner_main_module):
	with pytest.raises(ValueError, match='Repository name cannot be empty.'):
		asyncio.run(
			scanner_main_module.handle_topic_repository_cloned(
				key='example',
				value={'repository_name': ''},
				msg=None,
			)
		)


def test_handle_topic_repository_cloned_wraps_scan_errors(scanner_main_module, monkeypatch):
	async def fake_scan_repository(repository_name):
		raise RuntimeError('boom')

	monkeypatch.setattr(scanner_main_module, 'scan_repository', fake_scan_repository)

	with pytest.raises(ValueError, match='Repository scan failed: boom'):
		asyncio.run(
			scanner_main_module.handle_topic_repository_cloned(
				key='example',
				value={'repository_name': 'example'},
				msg=None,
			)
		)
