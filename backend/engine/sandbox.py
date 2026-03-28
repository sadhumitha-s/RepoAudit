import subprocess
import os
import logging
import shutil

logger = logging.getLogger(__name__)

class Sandbox:
    """
    Lightweight sandbox using Bubblewrap (bwrap).
    Falls back to a restricted subprocess if bwrap is missing.
    """
    
    def __init__(self, work_dir: str):
        self.work_dir = os.path.realpath(work_dir)
        self.has_bwrap = shutil.which("bwrap") is not None
        if not self.has_bwrap:
            logger.warning("Bubblewrap (bwrap) not found. Falling back to restricted subprocess.")

    def run(self, cmd: list[str], timeout: int = 60, allow_net: bool = False) -> subprocess.CompletedProcess:
        """Run a command in the sandbox."""
        if not self.has_bwrap:
            # Fallback (less secure)
            try:
                return subprocess.run(
                    cmd,
                    cwd=self.work_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"}
                )
            except subprocess.TimeoutExpired as e:
                return subprocess.CompletedProcess(cmd, 124, stdout=(e.stdout or ""), stderr=(e.stderr or ""))

        # Construct bwrap command
        bwrap_cmd = [
            "bwrap",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/sbin", "/sbin",
            "--ro-bind", "/etc/ssl", "/etc/ssl",
            "--ro-bind", "/etc/hosts", "/etc/hosts",
            "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", "/home",
            "--bind", self.work_dir, self.work_dir,
            "--chdir", self.work_dir,
            "--unshare-pid",
            "--unshare-uts",
            "--unshare-ipc",
        ]
        
        # Add lib64 if exists
        if os.path.exists("/lib64"):
            bwrap_cmd.extend(["--ro-bind", "/lib64", "/lib64"])
            
        # Add password/group if they exist
        for f in ["/etc/passwd", "/etc/group"]:
            if os.path.exists(f):
                bwrap_cmd.extend(["--ro-bind", f, f])

        if not allow_net:
            bwrap_cmd.append("--unshare-net")

        # Command to run
        bwrap_cmd.extend(cmd)

        try:
            return subprocess.run(
                bwrap_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            return subprocess.CompletedProcess(cmd, 124, stdout=stdout, stderr=stderr)
        except Exception as e:
            logger.error(f"Sandbox execution failed: {e}")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=str(e))
