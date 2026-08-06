import asyncio
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(scope='module')
def storage_main_module():
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
        sys.modules.pop('repository_storage_service.main', None)
        module = importlib.import_module('repository_storage_service.main')
    finally:
        patcher.undo()

    return module


def test_handle_topic_scan_started_pulls_existing_repository(storage_main_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    existing_repository = tmp_path / 'repositories' / 'example'
    existing_repository.mkdir(parents=True)

    fetch_calls = []
    reset_calls = []
    clean_calls = []

    class FakeOrigin:
        def fetch(self):
            fetch_calls.append('fetched')

    class FakeRepo:
        def __init__(self, path):
            self.path = path
            self.remotes = SimpleNamespace(origin=FakeOrigin())
            self.active_branch = SimpleNamespace(name='main')
            self.git = SimpleNamespace(
                reset=lambda *args: reset_calls.append(args),
                clean=lambda *args: clean_calls.append(args),
            )

        @classmethod
        def clone_from(cls, *_args, **_kwargs):
            raise AssertionError('clone_from should not be called for existing repositories')

    published_events = []

    async def fake_publish(event):
        published_events.append(event)

    monkeypatch.setattr(storage_main_module, 'Repo', FakeRepo)
    monkeypatch.setattr(
        storage_main_module,
        'event_producer',
        SimpleNamespace(publish=fake_publish),
    )

    asyncio.run(
        storage_main_module.handle_topic_scan_started(
            key='scan-key',
            value={'repository_url': 'https://github.com/acme/example.git'},
            msg=None,
        )
    )

    assert fetch_calls == ['fetched']
    assert reset_calls == [('--hard', 'origin/main')]
    assert clean_calls == [('-fd',)]
    assert len(published_events) == 1
    assert published_events[0].repository_name == 'example'
    assert published_events[0].key == 'example'


def test_handle_topic_scan_started_clones_missing_repository(storage_main_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    clone_calls = []

    class FakeRepo:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError('Repo should not be instantiated when cloning a new repository')

        @classmethod
        def clone_from(cls, repository_url, destination):
            clone_calls.append((repository_url, destination))

    published_events = []

    async def fake_publish(event):
        published_events.append(event)

    monkeypatch.setattr(storage_main_module, 'Repo', FakeRepo)
    monkeypatch.setattr(
        storage_main_module,
        'event_producer',
        SimpleNamespace(publish=fake_publish),
    )

    asyncio.run(
        storage_main_module.handle_topic_scan_started(
            key='scan-key',
            value={'repository_url': 'https://github.com/acme/new-repo.git'},
            msg=None,
        )
    )

    assert clone_calls == [
        ('https://github.com/acme/new-repo.git', Path('repositories/new-repo'))
    ]
    assert len(published_events) == 1
    assert published_events[0].repository_name == 'new-repo'
    assert published_events[0].key == 'new-repo'


def test_update_file_content_writes_the_new_content(storage_main_module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    file_path = tmp_path / 'repositories' / 'package' / 'manifest.txt'
    file_path.parent.mkdir(parents=True)
    file_path.write_text('old content')

    request = storage_main_module.UpdateFileContentRequest(new_content='new content')
    result = storage_main_module.update_file_content_endpoint(
        'package/manifest.txt', request
    )

    assert file_path.read_text() == 'new content'
    assert result.content == 'new content'
    assert result.path == Path('package/manifest.txt')