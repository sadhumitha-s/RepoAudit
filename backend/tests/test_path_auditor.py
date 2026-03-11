import pytest
from engine.path_auditor import audit_file, audit_directory


class TestAuditFile:
    def test_detects_windows_path(self, py_file):
        path = py_file("config.py", '''
DATA_DIR = "C:\\Users\\researcher\\data"
''')
        matches = audit_file(path)
        assert len(matches) >= 1
        assert matches[0].pattern_name == "Windows user path"

    def test_detects_linux_home(self, py_file):
        path = py_file("config.py", '''
DATA_DIR = "/home/user/datasets/imagenet"
''')
        matches = audit_file(path)
        assert len(matches) >= 1
        assert matches[0].pattern_name == "Linux home path"

    def test_detects_macos_path(self, py_file):
        path = py_file("config.py", '''
OUTPUT = "/Users/john/Documents/results"
''')
        matches = audit_file(path)
        assert len(matches) >= 1

    def test_ignores_urls(self, py_file):
        path = py_file("download.py", '''
URL = "https://home.example.com/Users/data"
''')
        matches = audit_file(path)
        assert len(matches) == 0

    def test_ignores_system_paths(self, py_file):
        path = py_file("config.py", '''
BIN = "/usr/local/bin/python"
''')
        matches = audit_file(path)
        assert len(matches) == 0

    def test_empty_file(self, py_file):
        path = py_file("empty.py", "")
        matches = audit_file(path)
        assert len(matches) == 0

    def test_documents_path(self, py_file):
        path = py_file("loader.py", '''
path = "/mnt/Documents/data.csv"
''')
        matches = audit_file(path)
        assert len(matches) >= 1


class TestAuditDirectory:
    def test_flags_hardcoded_paths(self, tmp_repo, py_file):
        py_file("config.py", '''
DATA = "C:\\Users\\me\\data"
OUTPUT = "/home/me/output"
''')
        issues = audit_directory(str(tmp_repo))
        assert len(issues) >= 2
        assert all(i.rule == "hardcoded_path" for i in issues)

    def test_clean_repo(self, tmp_repo, py_file):
        py_file("config.py", '''
import os
DATA = os.environ.get("DATA_DIR", "./data")
''')
        issues = audit_directory(str(tmp_repo))
        assert len(issues) == 0