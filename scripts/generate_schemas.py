import json
from pathlib import Path

from trustflow.domain.models import DraftAnswer, Questionnaire, ReviewDecision, SourceDocument

target = Path("schemas")
target.mkdir(exist_ok=True)
for model in (SourceDocument, Questionnaire, DraftAnswer, ReviewDecision):
    path = target / f"{model.__name__}.schema.json"
    path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n")
    print(path)
