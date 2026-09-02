"""FastAPI application factory for the live TunerOS telemetry service."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from tuneros.api.models import (
    ServiceStateEventResponse,
    SessionDetailResponse,
    SessionReplayResponse,
    SessionSummaryResponse,
    SignalDefinitionResponse,
    SignalHistoryResponse,
    SignalResponse,
    TelemetrySnapshotResponse,
    TelemetrySourceResponse,
    TelemetryStatisticsResponse,
    TelemetryStatusResponse,
)
from tuneros.api.serialization import (
    serialize_definition,
    serialize_initial_snapshot,
    serialize_sample,
    serialize_service_state,
    serialize_session_detail,
    serialize_session_summary,
    serialize_snapshot,
    serialize_statistics,
    serialize_update,
)
from tuneros.session import SessionCatalog, SessionError
from tuneros.telemetry import (
    SignalKey,
    SubscriberClosed,
    TelemetrySchemaError,
    TelemetryService,
    TelemetryServiceConfig,
    TelemetryServiceState,
    TelemetryServiceStateUpdate,
    TelemetryUpdate,
)

API_PREFIX = "/api/v1"
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8_000
DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def create_app(
    service: TelemetryService | None = None,
    *,
    config: TelemetryServiceConfig | None = None,
    autostart: bool = True,
    session_catalog: SessionCatalog | None = None,
    initial_replay_session_id: str | None = None,
) -> FastAPI:
    if service is not None and config is not None:
        raise ValueError("pass service or config, not both")
    telemetry_service = service or TelemetryService(config)
    sessions = session_catalog or SessionCatalog()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if initial_replay_session_id is not None:
            reader = sessions.reader(initial_replay_session_id)
            telemetry_service.start_replay(
                reader.frames,
                session_id=reader.manifest.session_id,
                session_name=reader.manifest.name,
                wait_for_subscriber=True,
            )
        elif autostart:
            telemetry_service.start()
        try:
            yield
        finally:
            telemetry_service.stop()

    app = FastAPI(
        title="TunerOS Telemetry API",
        version="1.0.0",
        description="Live or replayed decoded telemetry from synthetic TunerOS CAN.",
        lifespan=lifespan,
    )
    app.state.telemetry_service = telemetry_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEFAULT_CORS_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    def resolve_unique_signal(signal_name: str) -> SignalKey:
        try:
            key = telemetry_service.catalog.find_unique_signal(signal_name)
        except TelemetrySchemaError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if key is None:
            raise HTTPException(status_code=404, detail=f"unknown signal {signal_name!r}")
        return key

    def resolve_canonical_signal(message_name: str, signal_name: str) -> SignalKey:
        key = SignalKey(message_name, signal_name)
        if telemetry_service.catalog.get(key) is None:
            raise HTTPException(
                status_code=404,
                detail=f"unknown signal {message_name}.{signal_name}",
            )
        return key

    def signal_response(key: SignalKey) -> SignalResponse:
        definition = telemetry_service.catalog.require(key)
        sample, freshness = telemetry_service.latest(key)
        return SignalResponse(
            definition=serialize_definition(definition),
            sample=None if sample is None else serialize_sample(sample, freshness),
            freshness=freshness,
        )

    def history_response(key: SignalKey, limit: int | None) -> SignalHistoryResponse:
        if limit is not None and limit > telemetry_service.config.history_capacity:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"limit cannot exceed configured history capacity "
                    f"{telemetry_service.config.history_capacity}"
                ),
            )
        return SignalHistoryResponse(
            definition=serialize_definition(telemetry_service.catalog.require(key)),
            samples=[serialize_sample(sample) for sample in telemetry_service.history(key, limit)],
        )

    @app.get(f"{API_PREFIX}/status", response_model=TelemetryStatusResponse)
    def get_status() -> TelemetryStatusResponse:
        status = telemetry_service.status()
        return TelemetryStatusResponse(
            service_state=status.state,
            gateway_connected=status.gateway_connected,
            last_error=status.last_error,
            latest_timestamp_microseconds=status.statistics.latest_timestamp_microseconds,
            total_frames=status.statistics.total_frames,
            total_signal_updates=status.statistics.total_signal_updates,
        )

    @app.get(f"{API_PREFIX}/source", response_model=TelemetrySourceResponse)
    def get_source() -> TelemetrySourceResponse:
        source = telemetry_service.source_status()
        return TelemetrySourceResponse(
            mode=source.mode,
            session_id=source.session_id,
            session_name=source.session_name,
            recording=source.recording,
            recorded_frame_count=source.recorded_frame_count,
        )

    @app.get(f"{API_PREFIX}/sessions", response_model=list[SessionSummaryResponse])
    def get_sessions() -> list[SessionSummaryResponse]:
        try:
            return [
                serialize_session_summary(manifest, dbc_compatible=sessions.compatibility(manifest))
                for manifest in sessions.list()
            ]
        except SessionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get(f"{API_PREFIX}/sessions/{{session_id}}", response_model=SessionDetailResponse)
    def get_session(session_id: str) -> SessionDetailResponse:
        try:
            reader = sessions.reader(session_id, require_compatible_dbc=False)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except SessionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return serialize_session_detail(
            reader.manifest, dbc_compatible=sessions.compatibility(reader.manifest)
        )

    @app.post(
        f"{API_PREFIX}/sessions/{{session_id}}/replay",
        response_model=SessionReplayResponse,
        status_code=202,
    )
    def replay_session(session_id: str) -> SessionReplayResponse:
        try:
            reader = sessions.reader(session_id)
            telemetry_service.start_replay(
                reader.frames,
                session_id=reader.manifest.session_id,
                session_name=reader.manifest.name,
                wait_for_subscriber=True,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except SessionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return SessionReplayResponse(
            session_id=reader.manifest.session_id,
            session_name=reader.manifest.name,
        )

    @app.get(f"{API_PREFIX}/catalog", response_model=list[SignalDefinitionResponse])
    def get_catalog() -> list[SignalDefinitionResponse]:
        return [
            serialize_definition(definition) for definition in telemetry_service.catalog.definitions
        ]

    @app.get(f"{API_PREFIX}/telemetry", response_model=TelemetrySnapshotResponse)
    def get_telemetry() -> TelemetrySnapshotResponse:
        return serialize_snapshot(telemetry_service.snapshot(), telemetry_service)

    @app.get(f"{API_PREFIX}/statistics", response_model=TelemetryStatisticsResponse)
    def get_statistics() -> TelemetryStatisticsResponse:
        return serialize_statistics(telemetry_service.statistics(), telemetry_service)

    @app.get(f"{API_PREFIX}/signals/{{signal_name}}", response_model=SignalResponse)
    def get_signal(signal_name: str) -> SignalResponse:
        return signal_response(resolve_unique_signal(signal_name))

    @app.get(
        f"{API_PREFIX}/messages/{{message_name}}/signals/{{signal_name}}",
        response_model=SignalResponse,
    )
    def get_canonical_signal(message_name: str, signal_name: str) -> SignalResponse:
        return signal_response(resolve_canonical_signal(message_name, signal_name))

    @app.get(
        f"{API_PREFIX}/signals/{{signal_name}}/history",
        response_model=SignalHistoryResponse,
    )
    def get_signal_history(
        signal_name: str,
        limit: Annotated[int | None, Query(gt=0)] = None,
    ) -> SignalHistoryResponse:
        return history_response(resolve_unique_signal(signal_name), limit)

    @app.get(
        f"{API_PREFIX}/messages/{{message_name}}/signals/{{signal_name}}/history",
        response_model=SignalHistoryResponse,
    )
    def get_canonical_signal_history(
        message_name: str,
        signal_name: str,
        limit: Annotated[int | None, Query(gt=0)] = None,
    ) -> SignalHistoryResponse:
        return history_response(resolve_canonical_signal(message_name, signal_name), limit)

    @app.websocket(f"{API_PREFIX}/ws/telemetry")
    async def telemetry_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        subscription, snapshot, status = telemetry_service.subscribe(asyncio.get_running_loop())
        try:
            initial = serialize_initial_snapshot(snapshot, telemetry_service)
            await websocket.send_json(initial.model_dump(mode="json"))
            if status.state in (TelemetryServiceState.COMPLETED, TelemetryServiceState.FAILED):
                terminal = ServiceStateEventResponse(
                    state=status.state,
                    error=status.last_error,
                )
                await websocket.send_json(terminal.model_dump(mode="json"))
                await websocket.close(
                    code=1000 if status.state is TelemetryServiceState.COMPLETED else 1011
                )
                return

            while True:
                item = await subscription.receive()
                if isinstance(item, SubscriberClosed):
                    await websocket.close(code=1013, reason=item.reason)
                    return
                if isinstance(item, TelemetryUpdate):
                    event = serialize_update(item)
                elif isinstance(item, TelemetryServiceStateUpdate):
                    event = serialize_service_state(item)
                else:  # pragma: no cover - closed union is exhaustive
                    raise AssertionError("unknown telemetry subscriber item")
                await websocket.send_json(event.model_dump(mode="json"))
                if isinstance(item, TelemetryServiceStateUpdate) and item.state in (
                    TelemetryServiceState.COMPLETED,
                    TelemetryServiceState.FAILED,
                    TelemetryServiceState.STOPPED,
                ):
                    await websocket.close(
                        code=1000 if item.state is not TelemetryServiceState.FAILED else 1011
                    )
                    return
        except WebSocketDisconnect:
            return
        finally:
            subscription.close()

    return app
