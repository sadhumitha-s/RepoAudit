import os
import json
import pytest
from unittest.mock import patch, MagicMock
from engine.decay_auditor import audit_directory, DecayAuditResult

@pytest.fixture
def mock_repo(tmp_path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("numpy==1.21.0\npandas==1.3.0\nrequests>=2.25.1\n")
    return str(tmp_path)


@patch("urllib.request.urlopen")
def test_decay_audit_success(mock_urlopen, mock_repo):
    # Mocking responses for numpy and pandas
    def mock_response(req, **kwargs):
        url = req.full_url
        mock = MagicMock()
        mock.status = 200
        
        if "numpy" in url:
            data = {
                "info": {"yanked": False, "yanked_reason": None},
                "vulnerabilities": [{"id": "CVE-2021-33229"}],
                "urls": [{"upload_time_iso_8601": "2021-06-22T21:19:15.358509Z"}]
            }
        elif "pandas" in url:
            data = {
                "info": {"yanked": True, "yanked_reason": "Broken release"},
                "vulnerabilities": [],
                "urls": [{"upload_time_iso_8601": "2021-07-02T13:46:16.890691Z"}]
            }
        else:
            mock.status = 404
            data = {}
            
        mock.read.return_value = json.dumps(data).encode("utf-8")
        # Need to return a context manager for `with`
        mock.__enter__.return_value = mock
        return mock
        
    mock_urlopen.side_effect = mock_response

    result, issues = audit_directory(mock_repo)

    assert result is not None
    assert "pandas" in result.yanked_packages
    assert result.yanked_packages["pandas"] == "1.3.0"
    
    assert "numpy" in result.cve_packages
    assert "CVE-2021-33229" in result.cve_packages["numpy"]

    assert len(issues) == 2
    issue_msgs = [i.message for i in issues]
    assert any("yanked" in m for m in issue_msgs)
    assert any("CVEs" in m for m in issue_msgs)
    
    # Check that age calculations and metrics are somewhat populated
    assert result.avg_package_age_days > 0
    assert result.shelf_life_days >= 0
    assert result.time_to_break_days >= 0
    assert len(result.decay_curve) == 5

def test_decay_audit_no_requirements(tmp_path):
    result, issues = audit_directory(str(tmp_path))
    assert not result.yanked_packages
    assert not result.cve_packages
    assert not issues
