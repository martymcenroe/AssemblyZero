"""The parsing and prompt halves of tools/agy_exit_probe.py (#4510).

The probe's calls are real and run by hand; what is tested here is everything
that decides what a row says, so a wrong reading cannot pass as a finding.
"""

import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "tools" / "agy_exit_probe.py"
spec = importlib.util.spec_from_file_location("agy_exit_probe", TOOL)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize("size", [200, 2_000, 110_000])
def test_content_is_exactly_the_size_asked(size):
    assert len(probe.build_content(size)) == size


def test_content_starts_with_the_instruction():
    assert probe.build_content(5_000).startswith(probe.INSTRUCTION)


def test_a_long_reply_is_asked_for_by_function_count():
    content = probe.build_content(50_000, reply_lines=300)
    assert len(content) == 50_000
    assert content.startswith(probe.COPY_INSTRUCTION.format(k=300))


def test_too_small_a_size_is_refused():
    with pytest.raises(ValueError):
        probe.build_content(10)


def test_prompt_is_composed_as_the_transport_composes_it():
    prompt = probe.compose_prompt("gemini-3.8-flash-high", "body")
    assert prompt.startswith("You are gemini-3.8-flash-high.\n\n<system_instruction>\n")
    assert prompt.endswith("<user_content>\nbody\n</user_content>")


def test_stat_is_read_from_the_last_parenthesis():
    # A command name holding a space and a parenthesis must not shift fields.
    fields = ["S", "10", "4242"] + ["0"] * 14 + ["7"]
    text = "4243 (agy (lang) srv) " + " ".join(fields)
    stat = probe.parse_stat(text)
    assert stat == {"pid": 4243, "comm": "agy (lang) srv", "state": "S",
                    "ppid": 10, "pgrp": 4242, "threads": 7}


def test_tcp_table_maps_inode_to_endpoints():
    text = (
        "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt"
        "   uid  timeout inode\n"
        "   0: 0100007F:1F90 0101A8C0:01BB 01 00000000:00000000 00:00000000 00000000"
        "  1000        0 98765 1 0000000000000000 20 4 30 10 -1\n"
    )
    assert probe.parse_tcp_table(text) == {
        "98765": {"local": "0100007F:1F90", "remote": "0101A8C0:01BB", "state": "01"}
    }


def test_ipv4_endpoint_is_decoded():
    assert probe.hex_endpoint("0100007F:1F90") == "127.0.0.1:8080"
    assert probe.hex_endpoint("0101A8C0:01BB") == "192.168.1.1:443"


def test_log_tail_starts_at_the_completion_signal():
    log = "a\nb\nStream goroutine exited for x, sending completion signal\nc\nd\n"
    assert probe.log_tail_after_answer(log) == [
        "Stream goroutine exited for x, sending completion signal", "c", "d"]


def test_glog_clock_is_read_and_other_lines_are_not():
    assert probe.log_clock("I1101 17:16:00.463432      46 store_client.go:714] x") == "17:16:00"
    assert probe.log_clock("E1102 01:23:29.052762     194 file_watcher.go:194] y") == "01:23:29"
    assert probe.log_clock("plain text") is None


def test_an_agy_log_is_read_for_its_end(tmp_path):
    log = tmp_path / "cli-20261101_171600.log"
    log.write_text(
        "I1101 17:16:00.463432 46 store_client.go:714] summary store: starting\n"
        "E1101 17:16:01.000000 46 store_client.go:760] upsert failed: database is locked\n"
        "I1101 17:17:02.079977 845 server.go:1278] Stream goroutine exited, sending completion signal\n"
        "I1101 17:17:05.000000 46 store_client.go:764] summary store: reconciliation complete\n"
    )
    row = probe.read_agy_log(log)
    assert row["start"] == "17:16:00" and row["end"] == "17:17:05"
    assert row["answered_at"] == "17:17:02" and row["reconciled_at"] == "17:17:05"
    assert row["lock_errors"] == 1


def test_log_tail_without_the_signal_is_the_last_lines():
    log = "\n".join(str(i) for i in range(40))
    assert probe.log_tail_after_answer(log, limit=3) == ["37", "38", "39"]
