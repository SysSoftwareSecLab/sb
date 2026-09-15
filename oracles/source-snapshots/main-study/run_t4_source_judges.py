"""Finite resumable source-judge collection for the frozen T4 manifest."""
import fcntl
import hashlib
import json
from pathlib import Path
import sys


P = Path(__file__).resolve().parent
R = P.parents[3]
RUN = R / "05_formal/main_natural_384_v1"
METHODS = RUN / "methods"
FORMAL = P.parent / "formal_replacement_v2"
sys.path.insert(0, str(FORMAL))
import collect


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stop():
    if (METHODS / "USER_STOP.json").exists() or (METHODS / "TECHNICAL_HOLD.json").exists():
        raise RuntimeError("EXPLICIT_T4_STOP_OR_TECHNICAL_HOLD")


def parse(text, obligations, source):
    try:
        obj = json.loads(text)
        rows = obj["obligations"]
        expected = set(obligations)
        lines = len(source.splitlines())
        if not isinstance(rows, list) or len(rows) != len(expected) or {x["id"] for x in rows} != expected:
            raise ValueError("Obligation IDs missing, duplicate, or extra")
        for row in rows:
            if row["label"] not in {"C", "V", "U", "NA"}:
                raise ValueError("Invalid label")
            if not isinstance(row["reason"], str) or not row["reason"].strip():
                raise ValueError("Missing reason")
            if not isinstance(row["source_lines"], list) or any(type(x) is not int or x < 1 or x > lines for x in row["source_lines"]):
                raise ValueError("Invalid source line")
        return {"status": "VALID_STRUCTURED_PREDICTIONS", "predictions": rows}
    except (ValueError, TypeError, KeyError) as exc:
        return {
            "status": "INVALID_STRUCTURED_RESPONSE",
            "predictions": None,
            "parse_error": str(exc),
            "policy": "Original response retained; no scientific retry and no format normalization.",
        }


def zero_call_check(manifest):
    slots = manifest["source_judge"]["slots"]
    assert len(slots) == 798
    assert len({x["judge_slot_id"] for x in slots}) == 798
    objects = {x["object_id"]: x for x in manifest["objects"]}
    for item in slots:
        request_path = Path(item["request"])
        source_path = Path(item["source"])
        assert sha(request_path) == item["request_sha256"]
        assert sha(source_path) == item["source_sha256"]
        payload = read(request_path)
        assert payload["model"] == manifest["source_judge"]["profiles"][item["judge"]]["model"]
        content = json.loads(payload["messages"][1]["content"])
        assert set(content) == {"public_api_and_label_guide", "public_spec", "obligations", "numbered_source"}
        assert set(content["obligations"]) == set(item["obligations"])
        fixture = json.dumps({"obligations": [
            {"id": x, "label": "U", "source_lines": [], "reason": "synthetic parser fixture"}
            for x in item["obligations"]
        ]})
        assert parse(fixture, item["obligations"], source_path.read_text())["status"] == "VALID_STRUCTURED_PREDICTIONS"
        assert objects[item["object_id"]]["judge_eligible"]
    report = {
        "status": "PASS_ZERO_CALL_CHECK",
        "slots": len(slots),
        "network_calls": 0,
        "synthetic_predictions_not_research_data": True,
        "raw_response_final": True,
        "scientific_retries": 0,
        "transport_resume_only": True,
    }
    write(METHODS / "source_judge/ZERO_CALL_CHECK.json", report)
    return report


def main(run=False):
    manifest_path = METHODS / "T4_METHOD_MANIFEST.json"
    manifest = read(manifest_path)
    assert manifest["status"] == "T4_METHOD_INPUTS_FROZEN_ZERO_CALLS_ZERO_EXECUTIONS"
    zero_call_check(manifest)
    if not run:
        print(json.dumps(read(METHODS / "source_judge/ZERO_CALL_CHECK.json"), ensure_ascii=False))
        return
    collect.check_stop = stop
    profiles = manifest["source_judge"]["profiles"]
    slots = manifest["source_judge"]["slots"]
    completed = 0
    valid = 0
    invalid = 0
    lease_path = METHODS / "source_judge/collector.lock"
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    with lease_path.open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for item in slots:
            stop()
            request_path = Path(item["request"])
            source_path = Path(item["source"])
            assert sha(request_path) == item["request_sha256"]
            assert sha(source_path) == item["source_sha256"]
            payload = read(request_path)
            profile = profiles[item["judge"]]
            out = METHODS / "source_judge/results" / item["judge_slot_id"]
            result_path = out / "RESULT.json"
            if not result_path.exists():
                write(METHODS / "source_judge/STATUS.json", {
                    "status": "RUNNING", "completed": completed, "total": len(slots),
                    "valid": valid, "invalid": invalid, "active_slot": item["judge_slot_id"],
                })
                raw = collect.call_once(payload, profile, out)
                response, text, finish = collect.response_content(raw)
                result = parse(text, item["obligations"], source_path.read_text())
                result.update({
                    "object_id": item["object_id"],
                    "judge": item["judge"],
                    "scientific_call_made": True,
                    "response_model": response.get("model"),
                    "model_identity_matches": response.get("model") == profile["expected_response_model"],
                    "response_json_valid": bool(response),
                    "finish_reason": finish,
                    "usage": response.get("usage"),
                    "raw_sha256": sha(out / "RESPONSE.raw"),
                    "request_sha256": sha(request_path),
                    "source_sha256": sha(source_path),
                })
                write(result_path, result)
            result = read(result_path)
            assert result["request_sha256"] == sha(request_path)
            assert result["source_sha256"] == sha(source_path)
            assert result["raw_sha256"] == sha(out / "RESPONSE.raw")
            if result.get("response_json_valid") and not result.get("model_identity_matches"):
                raise RuntimeError("T4_JUDGE_MODEL_IDENTITY_CHANGED:" + item["judge"])
            completed += 1
            if result["status"] == "VALID_STRUCTURED_PREDICTIONS":
                valid += 1
            else:
                invalid += 1
            print(json.dumps({"completed": completed, "total": len(slots), "judge": item["judge"],
                              "status": result["status"]}, ensure_ascii=False), flush=True)
        write(METHODS / "source_judge/STATUS.json", {
            "status": "COMPLETE", "completed": completed, "total": len(slots),
            "valid": valid, "invalid": invalid, "scientific_retries": 0,
            "new_standalone_objects": 0,
        })


if __name__ == "__main__":
    main("--run" in sys.argv[1:])
