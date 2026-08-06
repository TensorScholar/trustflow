from trustflow import __version__
from trustflow.demo import run_demo

assert __version__ == "0.1.0rc2"
result = run_demo()
assert result["metrics"]["evidence_coverage"] > 0
assert result["audit_events"] >= 10
print("installed-wheel smoke passed")
