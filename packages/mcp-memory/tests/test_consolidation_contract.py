import uuid

import pytest
from pydantic import ValidationError

from mcp_memory.consolidation_contract import parse_consolidation_response


def test_valid_create_mutation() -> None:
    episode_id = str(uuid.uuid4())
    raw = f"""{{
        "mutations": [
            {{
                "action": "create",
                "statement": "Prefers leather over synthetic",
                "category": "style",
                "confidence": 0.6,
                "evidence_episode_ids": ["{episode_id}"],
                "reason": "3 leather product views + 1 purchase"
            }}
        ]
    }}"""
    response = parse_consolidation_response(raw)
    assert len(response.mutations) == 1
    assert response.mutations[0].action == "create"
    assert response.mutations[0].statement == "Prefers leather over synthetic"


def test_valid_deprecate_mutation() -> None:
    belief_id = str(uuid.uuid4())
    raw = f"""{{
        "mutations": [
            {{
                "action": "deprecate",
                "belief_id": "{belief_id}",
                "reason": "Contradicted by 3 recent full-price purchases"
            }}
        ]
    }}"""
    response = parse_consolidation_response(raw)
    assert response.mutations[0].belief_id == uuid.UUID(belief_id)


def test_empty_mutations_is_valid() -> None:
    response = parse_consolidation_response('{"mutations": []}')
    assert response.mutations == []


def test_create_without_statement_is_rejected() -> None:
    raw = """{
        "mutations": [
            {"action": "create", "category": "style", "confidence": 0.5, "reason": "x"}
        ]
    }"""
    with pytest.raises((ValidationError, ValueError)):
        parse_consolidation_response(raw)


def test_revise_without_belief_id_is_rejected() -> None:
    raw = """{
        "mutations": [
            {"action": "revise", "reason": "x"}
        ]
    }"""
    with pytest.raises((ValidationError, ValueError)):
        parse_consolidation_response(raw)


def test_malformed_json_is_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        parse_consolidation_response("not json at all")


def test_unknown_action_is_rejected() -> None:
    raw = """{
        "mutations": [
            {"action": "delete_everything", "reason": "x"}
        ]
    }"""
    with pytest.raises((ValidationError, ValueError)):
        parse_consolidation_response(raw)


def test_confidence_out_of_range_is_rejected() -> None:
    raw = """{
        "mutations": [
            {
                "action": "create",
                "statement": "x",
                "category": "style",
                "confidence": 1.5,
                "reason": "x"
            }
        ]
    }"""
    with pytest.raises((ValidationError, ValueError)):
        parse_consolidation_response(raw)
