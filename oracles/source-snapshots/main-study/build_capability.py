"""Build a deterministic, answer-hidden capability contrast for GLM-4.7/5."""
from pathlib import Path
import hashlib
import itertools
import json

P = Path(__file__).resolve().parent
R = P.parents[3]
GATE = R / "01_project/MAINLINE_ADMISSION_2026-09-12.json"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def topo_count(nodes, edges):
    total = 0
    for order in itertools.permutations(nodes):
        pos = {x: i for i, x in enumerate(order)}
        total += all(pos[a] < pos[b] for a, b in edges)
    return total


def main():
    assert json.loads(GATE.read_text())["status"] == "ACTIVE_HARD_GATE"
    items = []
    edge_sets = [
        [("A", "C"), ("B", "C")], [("A", "B"), ("A", "C")], [("A", "B"), ("B", "C")], [("A", "D"), ("B", "D"), ("C", "D")],
        [("A", "C"), ("B", "D")], [("A", "B"), ("C", "D")], [("A", "C"), ("C", "D"), ("B", "D")], [("A", "D"), ("B", "C"), ("C", "D")],
        [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")], [("A", "C"), ("B", "C"), ("B", "D")],
        [("A", "B"), ("A", "D"), ("C", "D")], [("A", "D"), ("B", "D")], [("A", "B"), ("B", "D"), ("C", "D")],
        [("A", "C"), ("C", "D")], [("A", "B"), ("B", "C"), ("A", "D")], [("A", "D"), ("B", "C")],
    ]
    nodes = ["A", "B", "C", "D"]
    for i, edges in enumerate(edge_sets, 1):
        items.append({"item_id": f"CAP-DAG-{i:02d}", "domain": "task_graph", "prompt": f"A task graph has nodes {nodes} and precedence edges {edges}. How many complete topological execution orders satisfy every edge? Return the integer as a string.", "answer": str(topo_count(nodes, edges))})

    cases = [
        ("LEFT acquires lock; LEFT releases lock", "VALID"),
        ("LEFT acquires lock; RIGHT releases lock", "WRONG_OWNER_RELEASE"),
        ("signal ready version 1 for part_0; wait returns that receipt; clear expected_version 1", "VALID"),
        ("signal ready version 1; clear expected_version 2", "WRONG_EVENT_VERSION"),
        ("LEFT grasps part_0; move LEFT with active receipt whose item_id is part_0", "VALID"),
        ("LEFT grasps part_0; move LEFT with active receipt whose item_id is part_1", "RECEIPT_ITEM_MISMATCH"),
        ("inspect route version 3 for part_0; grasp part_0 with that issued current observation", "VALID"),
        ("inspect route version 3 for part_0; fact invalidates to version 4; grasp with version 3 observation", "STALE_OBSERVATION"),
        ("LEFT acquires fixture then tool; releases tool then fixture", "VALID"),
        ("LEFT acquires fixture then tool; releases fixture while tool remains owned", "RESOURCE_ORDER_VIOLATION"),
        ("release part_0 at target; same coroutine immediately starts departure move", "VALID"),
        ("release part_0 at target; inspect occurs before same-arm departure", "DEPARTURE_NOT_IMMEDIATE"),
        ("two child tasks are created; both are awaited before return", "VALID"),
        ("two child tasks are created; one remains pending at return", "UNJOINED_CHILD"),
        ("wait ready receipt; carried move commits; then clear the exact version", "VALID"),
        ("wait ready receipt; clear it; then attempt the carried move with that receipt", "CLEARED_BEFORE_CONSUME"),
    ]
    for i, (trace, answer) in enumerate(cases, 1):
        items.append({"item_id": f"CAP-STATE-{i:02d}", "domain": "state_and_identity", "prompt": "Under the stated finite robot contract, classify this trace with exactly one supplied code. Trace: " + trace + ". Codes: VALID, WRONG_OWNER_RELEASE, WRONG_EVENT_VERSION, RECEIPT_ITEM_MISMATCH, STALE_OBSERVATION, RESOURCE_ORDER_VIOLATION, DEPARTURE_NOT_IMMEDIATE, UNJOINED_CHILD, CLEARED_BEFORE_CONSUME.", "answer": answer})

    schedules = [
        ([1, 4, 7], [2, 3, 8]), ([2, 5], [1, 6]), ([1, 2, 9], [3, 4, 5]), ([3, 6], [2, 7]),
        ([1, 5, 8], [2, 6, 7]), ([2, 4, 6], [1, 3, 5]), ([1, 6], [2, 3, 4]), ([4, 8], [1, 5, 9]),
        ([2, 7, 10], [1, 6, 8]), ([1, 3, 8], [2, 4, 7]), ([5, 9], [2, 6]), ([1, 4, 9], [3, 5, 8]),
        ([2, 3, 7], [1, 4, 6]), ([1, 7], [3, 5]), ([3, 4, 10], [1, 8, 9]), ([2, 6, 9], [1, 5, 7]),
    ]
    for i, (a, b) in enumerate(schedules, 1):
        merged = sorted([(t, "A" + str(j + 1)) for j, t in enumerate(a)] + [(t, "B" + str(j + 1)) for j, t in enumerate(b)])
        answer = ">".join(label for _, label in merged)
        items.append({"item_id": f"CAP-ASYNC-{i:02d}", "domain": "async_schedule", "prompt": f"Joined coroutine A completes its successive operations A1.. at logical times {a}; joined coroutine B completes B1.. at logical times {b}. All times are distinct and completion order is increasing logical time. Return the labels joined by > with no spaces.", "answer": answer})
    assert len(items) == 48 and len({x["item_id"] for x in items}) == 48
    profiles = {x["id"]: x for x in json.loads((P / "MODEL_PROFILES.json").read_text())}
    requests = []
    for item, profile_id, repeat in itertools.product(items, ["glm47", "glm5"], [1, 2]):
        profile = profiles[profile_id]
        payload = {
            "model": profile["model"], "thinking": {"type": "disabled"}, "temperature": 0.0, "max_tokens": 128, "stream": False,
            "messages": [
                {"role": "system", "content": "Answer the deterministic reasoning item. Return exactly one JSON object {\"answer\":\"...\"}; no Markdown, explanation, or extra keys."},
                {"role": "user", "content": item["prompt"]},
            ],
        }
        requests.append({"slot_id": f'{item["item_id"]}-{profile_id}-R{repeat}', "item_id": item["item_id"], "domain": item["domain"], "profile": profile_id, "repeat": repeat, "request": payload})
    requests.sort(key=lambda x: hashlib.sha256(("paper3-capability-v1/" + x["slot_id"]).encode()).hexdigest())
    assert len(requests) == 192
    public = [{k: v for k, v in x.items() if k != "answer"} for x in items]
    gold = {x["item_id"]: x["answer"] for x in items}
    write(P / "CAPABILITY_ITEMS_PUBLIC.json", public)
    write(P / "CAPABILITY_GOLD_PRIVATE.json", gold)
    write(P / "CAPABILITY_MANIFEST.json", requests)
    assert all("answer" not in x["request"] for x in requests)
    write(P / "CAPABILITY_STATUS.json", {"status": "COMPILED_NO_CALLS", "items": 48, "domains": 3, "glm47_glm5_outputs": 192, "repeats": 2, "gate_sha256": sha(GATE), "gold_field_absent_from_requests": True, "purpose": "Establish capability direction before interpreting same-series natural error migration; not a robotics safety outcome."})
    print(json.dumps({"items": 48, "requests": 192, "external_calls": 0}))


if __name__ == "__main__":
    main()
