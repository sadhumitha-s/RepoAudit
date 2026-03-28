import pytest
import json
from engine.notebook_analyzer import analyze_notebook

def test_analyze_notebook_ordering(tmp_path):
    # Cell 0: use x
    # Cell 1: define x
    nb_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["print(x)"],
                "metadata": {"line_number": 1}
            },
            {
                "cell_type": "code",
                "source": ["x = 42"],
                "metadata": {"line_number": 1}
            }
        ]
    }
    nb_file = tmp_path / "test_order.ipynb"
    nb_file.write_text(json.dumps(nb_content))
    
    issues = analyze_notebook(str(nb_file))
    
    ordering_issues = [i for i in issues if i.rule == "notebook_order"]
    assert len(ordering_issues) == 1
    assert "x" in ordering_issues[0].message

def test_analyze_notebook_dependencies(tmp_path):
    nb_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["!pip install torch"],
                "metadata": {}
            }
        ]
    }
    nb_file = tmp_path / "test_dep.ipynb"
    nb_file.write_text(json.dumps(nb_content))
    
    issues = analyze_notebook(str(nb_file))
    dep_issues = [i for i in issues if i.rule == "notebook_dependency"]
    assert len(dep_issues) == 1
    assert "Runtime dependency installation" in dep_issues[0].message

def test_analyze_notebook_global_mutation(tmp_path):
    nb_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["y = 10"],
                "metadata": {}
            }
        ]
    }
    nb_file = tmp_path / "test_mutation.ipynb"
    nb_file.write_text(json.dumps(nb_content))
    
    issues = analyze_notebook(str(nb_file))
    mutation_issues = [i for i in issues if i.rule == "notebook_global_mutation"]
    assert len(mutation_issues) == 1
    assert "global notebook state" in mutation_issues[0].message
