import subprocess
import pytest
import historical_section_oracle as oracle


def test_prefers_git_when_available(monkeypatch):
    raw=(oracle.FIXTURE/'section.py').read_bytes()
    monkeypatch.setattr(oracle.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a[0],0,raw,b''))
    assert oracle.load()==raw


def test_exact_fallback_for_missing_object(monkeypatch):
    monkeypatch.setattr(oracle.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a[0],128,b'',b'fatal: invalid object name'))
    assert oracle.load()==(oracle.FIXTURE/'section.py').read_bytes()


def test_rejects_unrelated_git_failure(monkeypatch):
    monkeypatch.setattr(oracle.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a[0],128,b'',b'fatal: permission denied'))
    with pytest.raises(subprocess.CalledProcessError):oracle.load()


def test_rejects_changed_successful_git_bytes(monkeypatch):
    monkeypatch.setattr(oracle.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a[0],0,b'changed',b''))
    with pytest.raises(AssertionError,match='bytes differ'):oracle.load()
