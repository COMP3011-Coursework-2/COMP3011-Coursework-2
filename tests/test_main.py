"""Tests for the REPL shell dispatch — input is faked, no crawl runs."""

from unittest.mock import MagicMock, patch

import pytest

import main as main_module
from indexer import Indexer
from main import Shell


@pytest.fixture
def loaded_shell() -> Shell:
    shell = Shell()
    shell.index = Indexer()
    shell.index.add_document("https://a/", "<html><body>good cat</body></html>")
    return shell


# --- help / unknown -----------------------------------------------------


def test_help_lists_commands(capsys):
    Shell()._dispatch("help", [])
    out = capsys.readouterr().out
    for cmd in ("build", "load", "print", "find"):
        assert cmd in out


def test_question_mark_aliases_help(capsys):
    Shell()._dispatch("?", [])
    out = capsys.readouterr().out
    assert "build" in out


def test_unknown_command_message(capsys):
    Shell()._dispatch("frobnicate", [])
    out = capsys.readouterr().out
    assert "unknown" in out.lower()


# --- guards before index is loaded --------------------------------------


def test_print_requires_loaded_index(capsys):
    Shell()._dispatch("print", ["good"])
    assert "not loaded" in capsys.readouterr().out


def test_find_requires_loaded_index(capsys):
    Shell()._dispatch("find", ["good"])
    assert "not loaded" in capsys.readouterr().out


# --- usage errors --------------------------------------------------------


def test_print_usage_error_with_zero_args(capsys, loaded_shell):
    loaded_shell._dispatch("print", [])
    assert "usage" in capsys.readouterr().out


def test_print_usage_error_with_too_many_args(capsys, loaded_shell):
    loaded_shell._dispatch("print", ["a", "b"])
    assert "usage" in capsys.readouterr().out


def test_find_usage_error_when_empty(capsys, loaded_shell):
    loaded_shell._dispatch("find", [])
    assert "usage" in capsys.readouterr().out


# --- happy-path dispatch -------------------------------------------------


def test_print_existing_word(capsys, loaded_shell):
    loaded_shell._dispatch("print", ["good"])
    out = capsys.readouterr().out
    assert "good:" in out
    assert "https://a/" in out


def test_find_returns_url(capsys, loaded_shell):
    loaded_shell._dispatch("find", ["good"])
    out = capsys.readouterr().out
    assert "https://a/" in out


def test_find_no_results_message(capsys, loaded_shell):
    loaded_shell._dispatch("find", ["zzz"])
    assert "no results" in capsys.readouterr().out


# --- load -----------------------------------------------------------------


def test_load_reads_index_from_disk(tmp_path, capsys, monkeypatch):
    from search import save_index
    idx = Indexer()
    idx.add_document("https://x/", "<html><body>hello</body></html>")
    path = tmp_path / "idx.json"
    save_index(idx, path)
    monkeypatch.setattr(main_module, "INDEX_PATH", path)

    shell = Shell()
    shell._dispatch("load", [])

    assert shell.index is not None
    assert shell.index.num_documents == 1
    assert "loaded 1 pages" in capsys.readouterr().out


# --- build (with crawler mocked) -----------------------------------------


def test_build_drives_crawler_and_saves(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(main_module, "INDEX_PATH", tmp_path / "out.json")

    fake_pages = [
        ("https://x/", "<html><body>hi</body></html>"),
        ("https://x/b", "<html><body>bye</body></html>"),
    ]

    class FakeCrawler:
        def __init__(self, *_args, **_kwargs):
            pass

        def crawl(self):
            yield from fake_pages

    monkeypatch.setattr(main_module, "Crawler", FakeCrawler)

    shell = Shell()
    shell._dispatch("build", [])

    assert (tmp_path / "out.json").exists()
    assert shell.index is not None
    assert shell.index.num_documents == 2
    out = capsys.readouterr().out
    assert "done" in out


# --- run() loop ----------------------------------------------------------


def test_run_handles_eof():
    shell = Shell()
    with patch("builtins.input", side_effect=EOFError):
        shell.run()  # exits cleanly


def test_run_exits_on_quit():
    shell = Shell()
    with patch("builtins.input", side_effect=["quit"]):
        shell.run()


def test_run_swallows_keyboard_interrupt(capsys):
    shell = Shell()
    # First input raises KI (continue), second is EOF (exit).
    with patch("builtins.input", side_effect=[KeyboardInterrupt, EOFError]):
        shell.run()


def test_run_recovers_from_command_exception(capsys, loaded_shell):
    # _build will raise because we haven't mocked Crawler; the REPL must
    # print the error and keep going.
    with patch("builtins.input", side_effect=["build", "exit"]):
        with patch.object(main_module, "Crawler") as crawler_cls:
            crawler_cls.return_value.crawl.side_effect = RuntimeError("boom")
            loaded_shell.run()
    assert "error: boom" in capsys.readouterr().out


def test_run_skips_blank_lines():
    shell = Shell()
    with patch("builtins.input", side_effect=["", "   ", EOFError]):
        shell.run()


def test_run_reports_parse_errors(capsys):
    shell = Shell()
    with patch("builtins.input", side_effect=['"unterminated', EOFError]):
        shell.run()
    assert "parse error" in capsys.readouterr().out


def test_main_returns_zero():
    with patch("builtins.input", side_effect=EOFError):
        assert main_module.main() == 0
