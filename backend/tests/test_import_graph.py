import os
import pytest
from engine.import_graph import (
    build_import_graph,
    audit_import_graph,
    _filepath_to_module,
)


class TestFilepathToModule:
    def test_simple(self, tmp_path):
        assert _filepath_to_module(
            str(tmp_path / "train.py"), str(tmp_path)
        ) == "train"

    def test_nested(self, tmp_path):
        assert _filepath_to_module(
            str(tmp_path / "utils" / "seed.py"), str(tmp_path)
        ) == "utils.seed"

    def test_init(self, tmp_path):
        assert _filepath_to_module(
            str(tmp_path / "utils" / "__init__.py"), str(tmp_path)
        ) == "utils"


class TestBuildImportGraph:
    def test_simple_import(self, tmp_path):
        (tmp_path / "train.py").write_text(
            "import utils\nutils.setup()\n"
        )
        (tmp_path / "utils.py").write_text(
            "def setup():\n    pass\n"
        )
        graph = build_import_graph(str(tmp_path))
        assert "train" in graph.modules
        assert "utils" in graph.modules
        assert len(graph.edges) >= 1
        assert any(e.source == "train" and e.target == "utils" for e in graph.edges)

    def test_detects_entry_point_by_main_guard(self, tmp_path):
        (tmp_path / "run.py").write_text(
            'if __name__ == "__main__":\n    print("hi")\n'
        )
        graph = build_import_graph(str(tmp_path))
        assert "run" in graph.entry_points

    def test_detects_entry_point_by_name(self, tmp_path):
        (tmp_path / "train.py").write_text("x = 1\n")
        graph = build_import_graph(str(tmp_path))
        assert "train" in graph.entry_points

    def test_no_python_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        graph = build_import_graph(str(tmp_path))
        assert len(graph.modules) == 0

    def test_circular_import(self, tmp_path):
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("import a\n")
        graph = build_import_graph(str(tmp_path))
        assert len(graph.circular_imports) > 0

    def test_no_circular_import(self, tmp_path):
        (tmp_path / "train.py").write_text("import utils\n")
        (tmp_path / "utils.py").write_text("import os\n")
        graph = build_import_graph(str(tmp_path))
        assert len(graph.circular_imports) == 0


class TestFlowTracing:
    def test_seed_in_utility_called_from_entry(self, tmp_path):
        (tmp_path / "train.py").write_text(
            "import utils\n"
            'if __name__ == "__main__":\n'
            "    utils.set_seed(42)\n"
        )
        (tmp_path / "utils.py").write_text(
            "import torch\n"
            "def set_seed(val):\n"
            "    torch.manual_seed(val)\n"
        )
        graph = build_import_graph(str(tmp_path))
        assert len(graph.flow_traces) >= 1
        trace = graph.flow_traces[0]
        assert "utils" in trace.reachable_modules
        assert len(trace.reachable_seed_calls) >= 1

    def test_seed_in_utility_not_called(self, tmp_path):
        (tmp_path / "train.py").write_text(
            "import utils\n"
            'if __name__ == "__main__":\n'
            "    print('training')\n"
        )
        (tmp_path / "utils.py").write_text(
            "import torch\n"
            "def set_seed(val):\n"
            "    torch.manual_seed(val)\n"
        )
        graph = build_import_graph(str(tmp_path))
        trace = graph.flow_traces[0]
        assert len(trace.unreachable_seed_calls) >= 1

    def test_unreachable_module_with_seed(self, tmp_path):
        (tmp_path / "train.py").write_text(
            'if __name__ == "__main__":\n'
            "    print('go')\n"
        )
        (tmp_path / "unused_utils.py").write_text(
            "import torch\n"
            "def setup():\n"
            "    torch.manual_seed(42)\n"
        )
        _, issues = audit_import_graph(str(tmp_path))
        assert any(
            "never imported" in i.message for i in issues
            if i.rule == "determinism"
        )


class TestAuditImportGraph:
    def test_circular_import_issue(self, tmp_path):
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("import a\n")
        _, issues = audit_import_graph(str(tmp_path))
        assert any(i.rule == "circular_import" for i in issues)

    def test_no_entry_point_issue(self, tmp_path):
        (tmp_path / "utils.py").write_text("x = 1\n")
        (tmp_path / "helpers.py").write_text("y = 2\n")
        _, issues = audit_import_graph(str(tmp_path))
        assert any(i.rule == "execution_flow" for i in issues)

    def test_clean_repo(self, tmp_path):
        (tmp_path / "train.py").write_text(
            "import torch\n"
            'if __name__ == "__main__":\n'
            "    torch.manual_seed(42)\n"
            "    x = torch.randn(10)\n"
        )
        _, issues = audit_import_graph(str(tmp_path))
        circular = [i for i in issues if i.rule == "circular_import"]
        assert len(circular) == 0