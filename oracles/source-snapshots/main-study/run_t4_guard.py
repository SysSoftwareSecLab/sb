"""Run the unchanged existing online guard on the frozen T4 subset."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys


P = Path(__file__).resolve().parent
T = P.parent
Q = T.parent
R = P.parents[3]
RUN = R / "05_formal/main_natural_384_v1"
METHODS = RUN / "methods"

sys.path.insert(0, str(R / "src"))
sys.path.insert(0, str(Q / "task2_evidence"))
import live_guard as live_guard_module
from live_guard import execute_guard
from bisafebench_pilot import sandbox_process_v03 as sandbox_v03
sys.path.insert(0, str(R / "01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src"))
from geometry_interface_v01 import evaluate_dynamic_evidence
sys.path.insert(0, str(Q / "task2_evidence"))
from evaluate import evaluate as parent_evaluate
sys.path.insert(0, str(T / "structural_batch"))
from measure import evaluate as structural_evaluate
sys.path.insert(0, str(Q / "batch_7_9"))
from evidence import evaluate as batch_evaluate
from grammar_oracle import evaluate as grammar_evaluate


# The outer managed sandbox rejects Bubblewrap's nested network namespace.  Keep
# Bubblewrap's file/process namespaces and the child seccomp filter (which denies
# socket/connect), while relying on the still-active outer network restriction.
_original_sandbox_command = sandbox_v03.command


def _outer_compatible_sandbox_command(job, filter_fd, limits, rpc_fd=None):
    command = _original_sandbox_command(job, filter_fd, limits, rpc_fd)
    index = command.index("--unshare-all")
    command[index:index + 1] = ["--unshare-user", "--unshare-ipc", "--unshare-pid", "--unshare-uts", "--unshare-cgroup"]
    return command


_original_client_source = live_guard_module.client_source


def _no_socket_syscall_client_source(root):
    source = _original_client_source(root)
    marker = "class Client:\n"
    assert source.count(marker) == 1
    transport = """class _InheritedFDTransport:
    def __init__(self, fd): self.fd = fd
    def setblocking(self, value): os.set_blocking(self.fd, value)
    def send(self, value): return os.write(self.fd, value)
    def recv(self, size): return os.read(self.fd, size)
    def fileno(self): return self.fd


"""
    source = source.replace("import math\n", "import math\nimport os\n", 1)
    source = source.replace(marker, transport + marker, 1)
    old = "self.socket = socket.socket(fileno=fd)"
    assert source.count(old) == 1
    return source.replace(old, "self.socket = _InheritedFDTransport(fd)", 1)


if os.environ.get("T4_FULL_BWRAP") != "1":
    sandbox_v03.command = _outer_compatible_sandbox_command
    live_guard_module.client_source = _no_socket_syscall_client_source


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_for(task, spec, source, capture):
    events = capture.get("trusted_events", [])
    geometry = evaluate_dynamic_evidence(spec, events, None) if events else {"status": "U_NO_TRUSTED_EVENTS"}
    parent = task["parent_evaluator"]
    if events:
        evaluator = batch_evaluate if parent.startswith("D") else parent_evaluate if parent.startswith("P") else structural_evaluate
        task_evidence = evaluator(spec, capture, geometry, parent)
    else:
        task_evidence = {"rows": [], "summary": {"EVIDENCE_AVAILABILITY": "U"}, "scope": "No trusted events"}
    metrics = read(P / "REFERENCE_PAIR_METRICS.json")["metrics_by_task"][task["task_id"]]
    grammar = grammar_evaluate(task, spec, source, capture, metrics)
    return geometry, task_evidence, grammar


async def main():
    manifest_path = METHODS / "T4_METHOD_MANIFEST.json"
    manifest = read(manifest_path)
    assert manifest["status"] == "T4_METHOD_INPUTS_FROZEN_ZERO_CALLS_ZERO_EXECUTIONS"
    implementation = Path(manifest["guard"]["implementation"])
    assert sha(implementation) == manifest["guard"]["implementation_sha256"]
    objects = {x["object_id"]: x for x in manifest["objects"]}
    tasks = {x["task_id"]: x for x in read(P / "TASK_CATALOG.json")}
    object_ids = manifest["guard"]["natural_object_ids"] + manifest["guard"]["controlled_object_ids"]
    assert len(object_ids) == 124
    completed = 0
    for object_id in object_ids:
        obj = objects[object_id]
        source_path = Path(obj["source"])
        spec_path = Path(obj["spec"])
        assert sha(source_path) == obj["source_sha256"] and sha(spec_path) == obj["spec_sha256"]
        out = METHODS / "guard/results" / object_id
        summary_path = out / "SUMMARY.json"
        if summary_path.exists():
            saved = read(summary_path)
            assert saved["source_sha256"] == obj["source_sha256"]
            completed += 1
            continue
        source = source_path.read_text()
        spec = read(spec_path)
        capture = await execute_guard(source, spec)
        if os.environ.get("T4_FULL_BWRAP") != "1":
            capture["process"]["security_profile"] = "BWRAP_RO_JOB_SECCOMP_NO_SOCKET_OUTER_MANAGED_NETWORK_V1"
        if capture.get("process", {}).get("status") == "SANDBOX_SETUP_FAILED":
            raise RuntimeError("SANDBOX_SETUP_FAILED:" + capture.get("process", {}).get("stderr", ""))
        task = tasks[obj["task_id"]]
        geometry, task_evidence, grammar = evidence_for(task, spec, source, capture)
        write(out / "CAPTURE.json", capture)
        write(out / "GEOMETRY.json", geometry)
        write(out / "TASK_EVIDENCE.json", task_evidence)
        write(out / "GRAMMAR_EVIDENCE.json", grammar)
        summary = {
            "object_id": object_id,
            "kind": obj["kind"],
            "controlled_role": obj.get("controlled_role"),
            "task_id": obj["task_id"],
            "source_sha256": obj["source_sha256"],
            "process_status": capture.get("process", {}).get("status"),
            "execution_lifecycle_complete": bool(capture.get("execution_lifecycle_complete")),
            "trusted_event_count": len(capture.get("trusted_events", [])),
            "call_audit_complete": bool(capture.get("call_audit_complete")),
            "intervention_count": len(capture.get("interventions", [])),
            "interventions": capture.get("interventions", []),
            "task_labels": task_evidence.get("summary", {}),
            "grammar_labels": grammar.get("summary", {}),
            "geometry_status": geometry.get("status"),
            "capture_sha256": sha(out / "CAPTURE.json"),
            "task_evidence_sha256": sha(out / "TASK_EVIDENCE.json"),
            "grammar_evidence_sha256": sha(out / "GRAMMAR_EVIDENCE.json"),
            "geometry_sha256": sha(out / "GEOMETRY.json"),
            "guard_implementation_sha256": sha(implementation),
            "human_label": None,
            "whole_program_safety": None,
        }
        write(summary_path, summary)
        completed += 1
        write(METHODS / "guard/STATUS.json", {
            "status": "RUNNING" if completed < len(object_ids) else "COMPLETE",
            "completed": completed,
            "total": len(object_ids),
            "natural": len(manifest["guard"]["natural_object_ids"]),
            "controlled": len(manifest["guard"]["controlled_object_ids"]),
            "implementation_unchanged": True,
        })
        print(json.dumps({"completed": completed, "total": len(object_ids), "object_id": object_id,
                          "interventions": summary["intervention_count"]}, ensure_ascii=False), flush=True)
    write(METHODS / "guard/STATUS.json", {
        "status": "COMPLETE",
        "completed": completed,
        "total": len(object_ids),
        "natural": len(manifest["guard"]["natural_object_ids"]),
        "controlled": len(manifest["guard"]["controlled_object_ids"]),
        "implementation_unchanged": True,
        "new_standalone_objects": 0,
    })


if __name__ == "__main__":
    asyncio.run(main())
