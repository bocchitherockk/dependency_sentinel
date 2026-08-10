import asyncio

from common.schemas.ManifestFile import ManifestFile
from common.schemas.ManifestFileSecurityReport import ManifestFileSecurityReport
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from events.schemas.DependenciesQueriedEvent import DependenciesQueriedEvent
from events.schemas.RepositoryScannedEvent import RepositoryScannedEvent
from registry_service import main as registry_main


def test_handle_topic_repository_scanned_publishes_dependencies_queried_event(monkeypatch):
    manifest_file = ManifestFile(path="requirements.txt", dependencies=[], dev_dependencies=[])
    event = RepositoryScannedEvent(repository_name="repo-one", detected_manifest_files=[manifest_file])
    published_events = []

    async def fake_get_manifest_file_update_context(value):
        assert value == manifest_file
        report = ManifestFileSecurityReport(path=value.path, dependencies=value.dependencies, dev_dependencies=value.dev_dependencies)
        return ManifestFileUpdateContext(
            current_manifest_file_report=report,
            candidate_manifest_file_report=report,
        )

    async def fake_publish(event):
        published_events.append(event)

    monkeypatch.setattr(registry_main, "get_manifest_file_update_context", fake_get_manifest_file_update_context)
    monkeypatch.setattr(registry_main.event_producer, "publish", fake_publish)

    asyncio.run(registry_main.handle_topic_repository_scanned("repo-one", event.model_dump(), None))

    assert len(published_events) == 1
    assert isinstance(published_events[0], DependenciesQueriedEvent)
    assert published_events[0].repository_name == "repo-one"
    assert published_events[0].manifest_files_update_context[0].current_manifest_file_report.path == "requirements.txt"


def test_lifespan_starts_and_stops_event_clients(monkeypatch):
    started = []
    stopped = []
    consumed = []
    created_tasks = []

    async def fake_start():
        started.append(True)

    async def fake_stop():
        stopped.append(True)

    def fake_consume(callback):
        consumed.append(callback)
        return "consume-task"

    def fake_create_task(coro):
        created_tasks.append(coro)
        return object()

    monkeypatch.setattr(registry_main.event_producer, "start", fake_start)
    monkeypatch.setattr(registry_main.event_consumer, "start", fake_start)
    monkeypatch.setattr(registry_main.event_producer, "stop", fake_stop)
    monkeypatch.setattr(registry_main.event_consumer, "stop", fake_stop)
    monkeypatch.setattr(registry_main.event_consumer, "consume", fake_consume)
    monkeypatch.setattr(registry_main.asyncio, "create_task", fake_create_task)

    async def run_lifespan():
        async with registry_main.lifespan(registry_main.app):
            assert len(started) == 2

    asyncio.run(run_lifespan())

    assert len(stopped) == 2
    assert len(created_tasks) == 1
    assert consumed and consumed[0] == registry_main.handle_topic_repository_scanned


def test_main_runs_uvicorn_with_registry_service_settings(monkeypatch):
    recorded = {}

    def fake_run(app, host, port):
        recorded["app"] = app
        recorded["host"] = host
        recorded["port"] = port

    monkeypatch.setattr(registry_main.uvicorn, "run", fake_run)

    registry_main.main()

    assert recorded["app"] is registry_main.app
    assert recorded["host"] == registry_main.services["registry-service"]["host"]
    assert recorded["port"] == registry_main.services["registry-service"]["port"]
