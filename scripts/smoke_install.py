from trustflow import __version__
from trustflow.demo import run_demo

assert __version__ == "0.1.0rc1"
result = run_demo()
assert result["metrics"]["evidence_coverage"] > 0
print("installed-wheel smoke passed")
