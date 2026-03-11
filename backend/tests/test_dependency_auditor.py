import os
import pytest
from engine.dependency_auditor import audit_directory


class TestDependencyAudit:
    def test_no_requirements_file(self, tmp_repo, py_file):
        py_file("train.py", "import torch\nimport numpy\n")
        result, issues = audit_directory(str(tmp_repo))
        assert result.has_requirements_txt is False
        assert any(i.severity == "critical" for i in issues)

    def test_pinned_requirements(self, tmp_repo, py_file):
        py_file("train.py", "import torch\n")
        with open(os.path.join(tmp_repo, "requirements.txt"), "w") as f:
            f.write("torch==2.1.0\nnumpy==1.24.0\n")
        result, issues = audit_directory(str(tmp_repo))
        assert result.has_requirements_txt is True
        assert result.pinned_count == 2
        assert result.unpinned_count == 0

    def test_unpinned_requirements(self, tmp_repo, py_file):
        py_file("train.py", "import torch\n")
        with open(os.path.join(tmp_repo, "requirements.txt"), "w") as f:
            f.write("torch>=2.0\nnumpy\n")
        result, issues = audit_directory(str(tmp_repo))
        assert result.unpinned_count == 2
        assert any("not pinned" in i.message for i in issues)

    def test_empty_requirements(self, tmp_repo, py_file):
        py_file("train.py", "import torch\n")
        with open(os.path.join(tmp_repo, "requirements.txt"), "w") as f:
            f.write("# Just a comment\n")
        result, issues = audit_directory(str(tmp_repo))
        assert result.total_deps == 0

    def test_detects_missing_deps(self, tmp_repo, py_file):
        py_file("train.py", "import torch\nimport wandb\n")
        with open(os.path.join(tmp_repo, "requirements.txt"), "w") as f:
            f.write("torch==2.1.0\n")
        result, issues = audit_directory(str(tmp_repo))
        assert "wandb" in result.missing_deps

    def test_dockerfile_bonus(self, tmp_repo, py_file):
        py_file("train.py", "import os\n")
        with open(os.path.join(tmp_repo, "requirements.txt"), "w") as f:
            f.write("requests==2.31.0\n")
        with open(os.path.join(tmp_repo, "Dockerfile"), "w") as f:
            f.write("FROM python:3.11\n")
        result, _ = audit_directory(str(tmp_repo))
        assert result.has_dockerfile is True

    def test_import_alias_mapping(self, tmp_repo, py_file):
        py_file("process.py", "import cv2\nfrom PIL import Image\n")
        with open(os.path.join(tmp_repo, "requirements.txt"), "w") as f:
            f.write("opencv-python==4.8.0\nPillow==10.0.0\n")
        result, issues = audit_directory(str(tmp_repo))
        # cv2 -> opencv-python and PIL -> Pillow should match
        assert "cv2" not in result.missing_deps
        assert "PIL" not in result.missing_deps