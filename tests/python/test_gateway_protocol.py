import queue
import socket
import threading

import pytest
from tuneros.can import (
    GATEWAY_HEADER_SIZE,
    GATEWAY_RECORD_SIZE,
    GatewayProtocolError,
    RawCanFrame,
    RawCanGatewayClient,
    decode_gateway_header,
    decode_gateway_record,
)

_GOLDEN_HEADER = bytes.fromhex("54 4E 43 52 01 00 00 00")
_GOLDEN_RECORD = bytes.fromhex("00 00 00 00 00 BC 61 4E 05 00 05 70 17 80 40 01 00 00 00")


def _record(timestamp: int, arbitration_id: int, payload: bytes) -> bytes:
    return (
        timestamp.to_bytes(8, "big")
        + arbitration_id.to_bytes(2, "big")
        + bytes([len(payload)])
        + payload.ljust(8, b"\x00")
    )


def _start_server(chunks: list[bytes]) -> tuple[int, threading.Thread, queue.Queue[BaseException]]:
    ready: queue.Queue[int] = queue.Queue()
    failures: queue.Queue[BaseException] = queue.Queue()

    def serve() -> None:
        try:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                ready.put(listener.getsockname()[1])
                connection, _ = listener.accept()
                with connection:
                    for chunk in chunks:
                        connection.sendall(chunk)
        except BaseException as error:
            failures.put(error)

    thread = threading.Thread(target=serve)
    thread.start()
    return ready.get(timeout=5), thread, failures


def _finish_server(thread: threading.Thread, failures: queue.Queue[BaseException]) -> None:
    thread.join(timeout=5)
    assert not thread.is_alive()
    if not failures.empty():
        raise failures.get_nowait()


def test_golden_header_and_record_are_independent_exact_vectors() -> None:
    assert len(_GOLDEN_HEADER) == GATEWAY_HEADER_SIZE
    assert len(_GOLDEN_RECORD) == GATEWAY_RECORD_SIZE
    assert decode_gateway_header(_GOLDEN_HEADER) is None
    assert decode_gateway_record(_GOLDEN_RECORD) == RawCanFrame(
        0x500, bytes.fromhex("70 17 80 40 01"), 12_345_678
    )


@pytest.mark.parametrize(
    "header,match",
    [
        (b"FAIL\x01\x00\x00\x00", "magic"),
        (b"TNCR\x02\x00\x00\x00", "version 2"),
        (b"TNCR\x01\x00\x00\x01", "reserved"),
        (b"TNCR", "requires 8 bytes"),
    ],
)
def test_invalid_headers_fail_clearly(header: bytes, match: str) -> None:
    with pytest.raises(GatewayProtocolError, match=match):
        decode_gateway_header(header)


def test_record_validation_and_payload_slicing() -> None:
    assert decode_gateway_record(_record(99, 0x123, b"\xaa\xbb")) == RawCanFrame(
        0x123, b"\xaa\xbb", 99
    )
    with pytest.raises(GatewayProtocolError, match="requires 19 bytes"):
        decode_gateway_record(bytes(18))
    with pytest.raises(GatewayProtocolError, match="arbitration ID"):
        decode_gateway_record(_record(0, 0x800, b""))
    invalid_dlc = bytes(10) + b"\x09" + bytes(8)
    with pytest.raises(GatewayProtocolError, match="DLC 9"):
        decode_gateway_record(invalid_dlc)


def test_socket_reader_handles_split_and_coalesced_stream_data_in_order() -> None:
    records = [
        _record(0, 0x500, b"\x01"),
        _record(0, 0x501, b"\x02\x03"),
        _record(10_000, 0x500, b"\x04"),
    ]
    stream = _GOLDEN_HEADER + b"".join(records)
    chunks = [stream[:2], stream[2:11], stream[11:25], stream[25:]]
    port, thread, failures = _start_server(chunks)

    with RawCanGatewayClient.connect(port=port, timeout=5) as client:
        frames = list(client.frames())

    _finish_server(thread, failures)
    assert frames == [
        RawCanFrame(0x500, b"\x01", 0),
        RawCanFrame(0x501, b"\x02\x03", 0),
        RawCanFrame(0x500, b"\x04", 10_000),
    ]


def test_record_boundary_eof_is_normal_but_partial_record_is_truncation() -> None:
    port, thread, failures = _start_server([_GOLDEN_HEADER])
    with RawCanGatewayClient.connect(port=port, timeout=5) as client:
        assert list(client.frames()) == []
    _finish_server(thread, failures)

    port, thread, failures = _start_server([_GOLDEN_HEADER + _GOLDEN_RECORD[:7]])
    with (
        RawCanGatewayClient.connect(port=port, timeout=5) as client,
        pytest.raises(GatewayProtocolError, match="received 7 of 19 bytes"),
    ):
        list(client.frames())
    _finish_server(thread, failures)
