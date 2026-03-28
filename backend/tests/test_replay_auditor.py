import unittest
from unittest.mock import MagicMock, patch
import os
import shutil
import tempfile
import subprocess

from engine.replay_auditor import audit_directory, ExecutionReplayResult
from models import Issue

class TestReplayAuditor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create a dummy requirements.txt
        with open(os.path.join(self.test_dir, "requirements.txt"), "w") as f:
            f.write("numpy\n")
        # Create a dummy main.py
        with open(os.path.join(self.test_dir, "main.py"), "w") as f:
            f.write("import numpy; print('hello')\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("engine.replay_auditor.Sandbox")
    def test_audit_flow_l3_success(self, MockSandbox):
        mock_sandbox = MockSandbox.return_value
        mock_sandbox.has_bwrap = True
        
        # Mock responses for L0, L1, L2
        def side_effect(cmd, timeout=60, allow_net=False):
            print(f"DEBUG: Mock running cmd: {cmd}")
            cmd_str = " ".join(str(part) for part in cmd)
            if "python3 -m venv" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            if "/pip install" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            if "-c" in cmd_str and "import" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout="Import success", stderr="")
            if "main.py" in cmd_str:
                # Simulate L3 by creating a file
                fpath = os.path.join(self.test_dir, "output.txt")
                with open(fpath, "w") as f:
                    f.write("data")
                print(f"DEBUG: Created file {fpath}")
                return subprocess.CompletedProcess(cmd, 0, stdout="Ran successfully", stderr="")
            return subprocess.CompletedProcess(cmd, 1)

        mock_sandbox.run.side_effect = side_effect
        
        result, issues = audit_directory(self.test_dir, claimed_commands=["python main.py"])
        print(f"DEBUG: Result levels: L0={result.l0_deps_install}, L1={result.l1_imports_success}, L2={result.l2_run_success}, L3={result.l3_outputs_produced}")
        print(f"DEBUG: Log:\n{result.log}")
        
        self.assertTrue(result.l0_deps_install)
        self.assertTrue(result.l1_imports_success)
        self.assertTrue(result.l2_run_success)
        self.assertTrue(result.l3_outputs_produced)
        self.assertEqual(result.highest_level, 3)

    @patch("engine.replay_auditor.Sandbox")
    def test_audit_flow_l0_failure(self, MockSandbox):
        mock_sandbox = MockSandbox.return_value
        mock_sandbox.has_bwrap = True
        mock_sandbox.run.return_value = subprocess.CompletedProcess([], 1, stdout="", stderr="pip install failed")
        
        result, issues = audit_directory(self.test_dir)
        
        self.assertFalse(result.l0_deps_install)
        self.assertEqual(result.highest_level, -1)
        self.assertTrue(any(i.rule == "execution" for i in issues))

if __name__ == "__main__":
    unittest.main()
