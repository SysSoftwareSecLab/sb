"""Independent dynamic fixed-AABB evidence for Stage 3 calibration traces.

This module does not import the forward runtime or its geometry adapter. It
reconstructs arm and object translations from the public spec plus trusted
action events, applies the published conditional contact lifecycle, uses a
closed-form swept-AABB test for continuous coverage, and asks PyBullet only for
independent pointwise corroboration.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import importlib.metadata
import math
from typing import Any


PROFILE = "DYNAMIC_FIXED_AABB_TRANSLATION_V01"
TOLERANCE_M = 1e-7
TIME_TOLERANCE_S = 1e-9


class GeometryInputError(ValueError):
    pass


def _pair_key(pair):
    return tuple(sorted(pair))


def _finite_vector(value, *, label):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise GeometryInputError(f"{label} must be a three-vector")
    result = []
    for item in value:
        if isinstance(item, bool) or type(item) not in (int, float) or not math.isfinite(item):
            raise GeometryInputError(f"{label} contains a non-finite or non-numeric coordinate")
        result.append(float(item))
    return result


def _lerp(first, second, fraction):
    return [a + (b - a) * fraction for a, b in zip(first, second)]


def _add(first, second):
    return [a + b for a, b in zip(first, second)]


def _subtract(first, second):
    return [a - b for a, b in zip(first, second)]


def _close(first, second, tolerance=TOLERANCE_M):
    return len(first) == len(second) and all(abs(a - b) <= tolerance for a, b in zip(first, second))


def box_signed_distance(first, second, half_first, half_second):
    gaps = [abs(a - b) - ha - hb for a, b, ha, hb in zip(first, second, half_first, half_second)]
    if max(gaps) > 0:
        return math.sqrt(sum(max(gap, 0.0) ** 2 for gap in gaps))
    return max(gaps)


def swept_aabb(first0, first1, second0, second1, half_first, half_second):
    """Exact-in-model interval intersection for two affine AABB centers."""
    low, high = 0.0, 1.0
    for a, b, c, d, ha, hb in zip(first0, first1, second0, second1, half_first, half_second):
        separation = a - c
        velocity = (b - a) - (d - c)
        extent = ha + hb
        if abs(velocity) < 1e-14:
            if abs(separation) > extent:
                return None
            continue
        enter, leave = sorted(((-extent - separation) / velocity,
                               (extent - separation) / velocity))
        low, high = max(low, enter), min(high, leave)
        if low > high + 1e-12:
            return None
    if low > high:
        return None
    return [max(0.0, low), min(1.0, high)]


@dataclass
class MoveSegment:
    operation_id: str
    arm: str
    pose: str
    start_index: int
    terminal_index: int | None
    start_time: float
    end_time: float
    start_xyz: list[float]
    end_xyz: list[float]
    target_xyz: list[float]
    completion_fraction: float
    terminal_phase: str
    candidate_task_id: str | None

    def position(self, at):
        if self.end_time <= self.start_time + TIME_TOLERANCE_S:
            return list(self.end_xyz)
        fraction = (at - self.start_time) / (self.end_time - self.start_time)
        return _lerp(self.start_xyz, self.end_xyz, min(1.0, max(0.0, fraction)))

    def record(self):
        return {
            "operation_id": self.operation_id,
            "arm": self.arm,
            "pose": self.pose,
            "event_indexes": [self.start_index, self.terminal_index],
            "time_interval_s": [self.start_time, self.end_time],
            "start_xyz_m": self.start_xyz,
            "end_xyz_m": self.end_xyz,
            "target_xyz_m": self.target_xyz,
            "completion_fraction": self.completion_fraction,
            "terminal_phase": self.terminal_phase,
            "candidate_task_id": self.candidate_task_id,
        }


@dataclass
class Attachment:
    object_id: str
    arm: str
    grasp_start_index: int
    grasp_complete_index: int
    grasp_start_time: float
    attached_at: float
    release_start_index: int | None
    release_complete_index: int | None
    released_at: float
    support_zone: str | None
    offset_xyz_m: list[float]

    def record(self):
        return {
            "object_id": self.object_id,
            "arm": self.arm,
            "grasp_event_indexes": [self.grasp_start_index, self.grasp_complete_index],
            "grasp_time_interval_s": [self.grasp_start_time, self.attached_at],
            "attachment_time_interval_s": [self.attached_at, self.released_at],
            "release_event_indexes": [self.release_start_index, self.release_complete_index],
            "support_zone": self.support_zone,
            "offset_xyz_m": self.offset_xyz_m,
        }


class TraceModel:
    def __init__(self, spec, events):
        self.spec = spec
        self.events = [dict(row) for row in events]
        self.errors = []
        self.permission_errors = []
        self.coordinates = {
            name: _finite_vector(value, label=f"pose {name}")
            for name, value in spec["world"]["pose_coordinates_m"].items()
        }
        self.solids = list(spec["world"]["modeled_solids"])
        self.arms = {body.removesuffix("_gripper"): body for body in self.solids
                     if body.endswith("_gripper")}
        self.objects = [body for body in self.solids if not body.endswith("_gripper")]
        self.sizes = {}
        gripper_half = _finite_vector(spec["world"]["gripper_half_size_m"], label="gripper half size")
        for body in self.solids:
            if body.endswith("_gripper"):
                self.sizes[body] = list(gripper_half)
            else:
                value = spec["world"].get("object_half_size_m", {}).get(body)
                self.sizes[body] = _finite_vector(value, label=f"half size {body}")
        self.initial = spec["pair_constants"]["initial"]
        self.initial_positions = {}
        for arm, body in self.arms.items():
            pose = self.initial.get(arm)
            if pose not in self.coordinates:
                raise GeometryInputError(f"Missing initial coordinate for arm {arm}")
            self.initial_positions[body] = list(self.coordinates[pose])
        self.object_placements = defaultdict(list)
        for object_id in self.objects:
            place = self.initial.get(object_id)
            if place not in self.coordinates:
                raise GeometryInputError(f"Missing initial coordinate for object {object_id}")
            self.initial_positions[object_id] = list(self.coordinates[place])
            self.object_placements[object_id].append((-math.inf, list(self.coordinates[place]), place))
        self._validate_events()
        # The public logical clock starts at zero.  A candidate can sleep
        # before its first robot call; that initial static interval is still
        # part of the physical proposition and must not disappear.
        self.trace_start = 0.0
        self.trace_end = self.events[-1]["time"] if self.events else 0.0
        self.moves = self._build_moves()
        self.attachments = self._build_attachments()
        self.reconstruction_checks = self._check_snapshots()

    def _validate_events(self):
        prior_time = -math.inf
        for expected_index, event in enumerate(self.events):
            if event.get("index") != expected_index:
                self.errors.append({"reason": "Non-contiguous trusted event index",
                                    "expected": expected_index, "observed": event.get("index")})
            value = event.get("time")
            if isinstance(value, bool) or type(value) not in (int, float) or not math.isfinite(value):
                self.errors.append({"reason": "Invalid trusted event time", "event_index": expected_index})
                continue
            event["time"] = float(value)
            if event["time"] < -TIME_TOLERANCE_S:
                self.errors.append({"reason": "Negative trusted event time", "event_index": expected_index})
            if event["time"] + TIME_TOLERANCE_S < prior_time:
                self.errors.append({"reason": "Regressing trusted event time", "event_index": expected_index})
            prior_time = event["time"]

    def _terminal_for(self, start):
        operation_id = start.get("operation_id")
        terminals = [row for row in self.events[start["index"] + 1:]
                     if row.get("operation_id") == operation_id
                     and row.get("action") == "move"
                     and row.get("phase") in {"complete", "timeout", "cancel", "fault"}]
        # AFTER_COMMIT produces complete followed by fault. The completed move
        # is the geometric terminal; the later fault changes control state only.
        completed = next((row for row in terminals if row.get("phase") == "complete"), None)
        return completed or (terminals[0] if terminals else None)

    def _arm_position_from(self, arm, at, built):
        body = self.arms[arm]
        candidates = [segment for segment in built[arm]
                      if segment.start_time - TIME_TOLERANCE_S <= at <= segment.end_time + TIME_TOLERANCE_S]
        if candidates:
            return candidates[-1].position(at)
        completed = [segment for segment in built[arm] if segment.end_time <= at + TIME_TOLERANCE_S]
        return list(completed[-1].end_xyz if completed else self.initial_positions[body])

    def _build_moves(self):
        built = {arm: [] for arm in self.arms}
        duration = float(self.spec["pair_constants"]["durations_s"]["move"])
        if not math.isfinite(duration) or duration <= 0:
            raise GeometryInputError("move duration must be finite and positive")
        for start in [row for row in self.events if row.get("action") == "move" and row.get("phase") == "start"]:
            arm = start.get("args", {}).get("arm")
            pose = start.get("args", {}).get("pose")
            if arm not in built or pose not in self.coordinates:
                self.errors.append({"reason": "Move references undeclared arm or pose", "event_index": start["index"]})
                continue
            if any(segment.start_time < start["time"] < segment.end_time - TIME_TOLERANCE_S
                   for segment in built[arm]):
                self.errors.append({"reason": "Overlapping moves for one arm", "event_index": start["index"], "arm": arm})
            start_xyz = self._arm_position_from(arm, start["time"], built)
            terminal = self._terminal_for(start)
            if terminal is None:
                end_time = self.trace_end
                fraction = min(1.0, max(0.0, (end_time - start["time"]) / duration)) if duration else 1.0
                phase, terminal_index = "INCOMPLETE_PREFIX", None
            else:
                end_time = terminal["time"]
                result = terminal.get("result") or {}
                phase, terminal_index = terminal["phase"], terminal["index"]
                elapsed_fraction = min(1.0, max(0.0, (end_time - start["time"]) / duration))
                fraction = 1.0 if phase == "complete" else elapsed_fraction
                reported_fraction = result.get("completion_fraction")
                if (isinstance(reported_fraction, bool) or type(reported_fraction) not in (int, float)
                        or not math.isfinite(reported_fraction)
                        or abs(float(reported_fraction) - fraction) > TIME_TOLERANCE_S):
                    self.errors.append({"reason": "Move receipt completion_fraction disagrees with public duration and event times",
                                        "event_index": terminal_index, "operation_id": start.get("operation_id"),
                                        "derived_fraction": fraction, "reported_fraction": reported_fraction})
                reported_committed = result.get("committed")
                expected_committed = phase == "complete" or (phase == "fault" and terminal.get("outcome") == "AFTER_COMMIT")
                if reported_committed is not expected_committed:
                    self.errors.append({"reason": "Move receipt commit state disagrees with terminal phase",
                                        "event_index": terminal_index, "operation_id": start.get("operation_id"),
                                        "expected_committed": expected_committed,
                                        "reported_committed": reported_committed})
                if phase == "complete" and abs((end_time - start["time"]) - duration) > TIME_TOLERANCE_S:
                    self.errors.append({"reason": "Committed move time disagrees with public duration",
                                        "event_index": terminal_index, "operation_id": start.get("operation_id"),
                                        "elapsed_s": end_time - start["time"], "duration_s": duration})
                expected_final_pose = pose if expected_committed else None
                if result.get("final_pose") != expected_final_pose:
                    self.errors.append({"reason": "Move receipt final_pose disagrees with independently derived commit state",
                                        "event_index": terminal_index, "operation_id": start.get("operation_id"),
                                        "expected_final_pose": expected_final_pose,
                                        "reported_final_pose": result.get("final_pose")})
            target = list(self.coordinates[pose])
            end_xyz = _lerp(start_xyz, target, fraction)
            segment = MoveSegment(
                operation_id=start.get("operation_id"), arm=arm, pose=pose,
                start_index=start["index"], terminal_index=terminal_index,
                start_time=start["time"], end_time=end_time,
                start_xyz=start_xyz, end_xyz=end_xyz, target_xyz=target,
                completion_fraction=fraction, terminal_phase=phase,
                candidate_task_id=start.get("candidate_task_id"),
            )
            built[arm].append(segment)
        return built

    def arm_position(self, arm, at):
        return self._arm_position_from(arm, at, self.moves)

    def _placement_before(self, object_id, at):
        candidates = [row for row in self.object_placements[object_id] if row[0] <= at + TIME_TOLERANCE_S]
        return list(candidates[-1][1])

    def _build_attachments(self):
        attachments = defaultdict(list)
        grasp_duration = float(self.spec["pair_constants"]["durations_s"].get("grasp", 0.0))
        release_duration = float(self.spec["pair_constants"]["durations_s"].get("release", 0.0))
        declared_offsets = self.spec["world"].get("grasp_offsets_m", {})
        if not isinstance(declared_offsets, dict):
            raise GeometryInputError("world.grasp_offsets_m must be an object when present")
        complete_grasps = [row for row in self.events
                           if row.get("action") == "grasp" and row.get("phase") == "complete"]
        for complete in complete_grasps:
            arm = complete.get("args", {}).get("arm")
            object_id = complete.get("args", {}).get("object_id")
            start = next((row for row in self.events[:complete["index"]]
                          if row.get("operation_id") == complete.get("operation_id")
                          and row.get("action") == "grasp" and row.get("phase") == "start"), None)
            if arm not in self.arms or object_id not in self.objects or start is None:
                self.errors.append({"reason": "Malformed completed grasp", "event_index": complete["index"]})
                continue
            result = complete.get("result")
            expected_value = {"held_by": arm, "item_id": object_id}
            receipt_valid = (
                isinstance(result, dict)
                and result.get("fact_id") == "grasp_state"
                and result.get("producer_operation_id") == complete.get("operation_id")
                and result.get("value") == expected_value
                and type(result.get("observed_at")) in (int, float)
                and abs(float(result["observed_at"]) - complete["time"]) <= TIME_TOLERANCE_S
            )
            duration_valid = (grasp_duration > 0
                              and abs((complete["time"] - start["time"]) - grasp_duration) <= TIME_TOLERANCE_S)
            if not receipt_valid or not duration_valid:
                self.errors.append({
                    "reason": "Completed grasp event disagrees with public duration or committed grasp receipt",
                    "event_index": complete["index"], "operation_id": complete.get("operation_id"),
                    "receipt_valid": receipt_valid, "duration_valid": duration_valid,
                })
            object_xyz = self._placement_before(object_id, complete["time"])
            arm_xyz = self.arm_position(arm, complete["time"])
            offset = _subtract(object_xyz, arm_xyz)
            declared_offset_raw = declared_offsets.get(
                f"{arm}|{object_id}", declared_offsets.get(object_id, [0.0, 0.0, 0.0])
            )
            declared_offset = _finite_vector(
                declared_offset_raw, label=f"declared grasp offset {arm}|{object_id}"
            )
            if not _close(offset, declared_offset):
                self.errors.append({
                    "reason": "Observed grasp offset is not the public declared grasp offset",
                    "event_index": complete["index"], "arm": arm, "object_id": object_id,
                    "observed_offset_xyz_m": offset,
                    "declared_offset_xyz_m": declared_offset,
                })
            releases = [row for row in self.events[complete["index"] + 1:]
                        if row.get("action") == "release" and row.get("phase") == "complete"
                        and row.get("args", {}).get("arm") == arm
                        and row.get("args", {}).get("object_id") == object_id]
            release = releases[0] if releases else None
            release_start = None
            if release is not None:
                release_start = next((row for row in self.events[complete["index"] + 1:release["index"]]
                                      if row.get("operation_id") == release.get("operation_id")
                                      and row.get("action") == "release" and row.get("phase") == "start"), None)
            released_at = release["time"] if release is not None else self.trace_end
            support_zone = release.get("args", {}).get("support_zone") if release is not None else None
            if release is not None:
                release_result = release.get("result")
                release_receipt_valid = (
                    isinstance(release_result, dict)
                    and release_result.get("method") == "release"
                    and release_result.get("operation_id") == release.get("operation_id")
                    and release_result.get("committed") is True
                    and release_result.get("status") == "COMMITTED"
                    and release_result.get("completion_fraction") == 1.0
                    and release_result.get("final_pose") == support_zone
                    and type(release_result.get("started_at")) in (int, float)
                    and type(release_result.get("finished_at")) in (int, float)
                    and abs(float(release_result["started_at"]) - release_start["time"]) <= TIME_TOLERANCE_S
                    and abs(float(release_result["finished_at"]) - release["time"]) <= TIME_TOLERANCE_S
                ) if release_start is not None else False
                release_duration_valid = (
                    release_start is not None and release_duration > 0
                    and abs((release["time"] - release_start["time"]) - release_duration) <= TIME_TOLERANCE_S
                )
                if not release_receipt_valid or not release_duration_valid:
                    self.errors.append({
                        "reason": "Completed release event disagrees with public duration or committed release receipt",
                        "event_index": release["index"], "operation_id": release.get("operation_id"),
                        "receipt_valid": release_receipt_valid,
                        "duration_valid": release_duration_valid,
                    })
            attachment = Attachment(
                object_id=object_id, arm=arm,
                grasp_start_index=start["index"], grasp_complete_index=complete["index"],
                grasp_start_time=start["time"], attached_at=complete["time"],
                release_start_index=release_start["index"] if release_start else None,
                release_complete_index=release["index"] if release else None,
                released_at=released_at, support_zone=support_zone,
                offset_xyz_m=offset,
            )
            attachments[object_id].append(attachment)
            if release is not None:
                released_xyz = _add(self.arm_position(arm, released_at), offset)
                if support_zone not in self.coordinates:
                    self.errors.append({"reason": "Release support has no declared coordinate",
                                        "event_index": release["index"], "support_zone": support_zone})
                elif not _close(released_xyz, self.coordinates[support_zone]):
                    self.errors.append({"reason": "Released object coordinate disagrees with support coordinate",
                                        "event_index": release["index"], "object_id": object_id,
                                        "reconstructed_xyz_m": released_xyz,
                                        "support_xyz_m": self.coordinates[support_zone]})
                self.object_placements[object_id].append((released_at, released_xyz, support_zone))
        return attachments

    def object_position(self, object_id, at):
        for attachment in self.attachments[object_id]:
            if attachment.attached_at - TIME_TOLERANCE_S <= at <= attachment.released_at + TIME_TOLERANCE_S:
                return _add(self.arm_position(attachment.arm, at), attachment.offset_xyz_m)
        return self._placement_before(object_id, at)

    def position(self, body, at):
        if body.endswith("_gripper"):
            return self.arm_position(body.removesuffix("_gripper"), at)
        return self.object_position(body, at)

    def _check_snapshots(self):
        checks, failures = 0, []
        expected_objects = {object_id: self.initial[object_id] for object_id in self.objects}
        expected_held = {arm: None for arm in self.arms}
        for event in self.events:
            state = event.get("scene_state")
            if not isinstance(state, dict):
                failures.append({"reason": "Missing scene_state", "event_index": event["index"]})
                continue
            # Runtime records complete events after their instantaneous commit.
            # Apply only the transition justified by the trusted action history,
            # then compare the snapshot's symbolic ownership at this exact index.
            if event.get("phase") == "complete" and event.get("action") == "grasp":
                arm = event.get("args", {}).get("arm")
                object_id = event.get("args", {}).get("object_id")
                if arm not in expected_held or object_id not in expected_objects:
                    failures.append({"reason": "Completed grasp references undeclared arm or object",
                                     "event_index": event["index"]})
                elif expected_held[arm] is not None or str(expected_objects[object_id]).startswith("HELD:"):
                    failures.append({"reason": "Completed grasp violates independently reconstructed ownership",
                                     "event_index": event["index"], "arm": arm, "object_id": object_id})
                else:
                    expected_held[arm] = object_id
                    expected_objects[object_id] = "HELD:" + arm
            if event.get("phase") == "complete" and event.get("action") == "release":
                arm = event.get("args", {}).get("arm")
                object_id = event.get("args", {}).get("object_id")
                support = event.get("args", {}).get("support_zone")
                if arm not in expected_held or object_id not in expected_objects or expected_held.get(arm) != object_id:
                    failures.append({"reason": "Completed release violates independently reconstructed ownership",
                                     "event_index": event["index"], "arm": arm, "object_id": object_id})
                else:
                    expected_held[arm] = None
                    expected_objects[object_id] = support

            observed_symbolic = state.get("objects", {})
            observed_held = state.get("held", {})
            for object_id in self.objects:
                checks += 1
                if observed_symbolic.get(object_id) != expected_objects[object_id]:
                    failures.append({"reason": "Trusted object state disagrees with event-derived attachment lifecycle",
                                     "event_index": event["index"], "object_id": object_id,
                                     "observed_state": observed_symbolic.get(object_id),
                                     "reconstructed_state": expected_objects[object_id]})
            for arm in self.arms:
                checks += 1
                if observed_held.get(arm) != expected_held[arm]:
                    failures.append({"reason": "Trusted held state disagrees with event-derived attachment lifecycle",
                                     "event_index": event["index"], "arm": arm,
                                     "observed_object": observed_held.get(arm),
                                     "reconstructed_object": expected_held[arm]})

            grippers = state.get("gripper_xyz_m", {})
            for arm in self.arms:
                checks += 1
                try:
                    observed = _finite_vector(grippers.get(arm), label=f"event {event['index']} gripper {arm}")
                except GeometryInputError as exc:
                    failures.append({"reason": str(exc), "event_index": event["index"]})
                    continue
                expected = self.arm_position(arm, event["time"])
                if not _close(observed, expected):
                    failures.append({"reason": "Trusted gripper coordinate disagrees with command reconstruction",
                                     "event_index": event["index"], "arm": arm,
                                     "observed_xyz_m": observed, "reconstructed_xyz_m": expected})
            observed_objects = state.get("object_xyz_m", {})
            for object_id in self.objects:
                checks += 1
                if object_id not in observed_objects:
                    failures.append({"reason": "Missing trusted object coordinate",
                                     "event_index": event["index"], "object_id": object_id})
                    continue
                try:
                    observed = _finite_vector(observed_objects[object_id],
                                              label=f"event {event['index']} object {object_id}")
                except GeometryInputError as exc:
                    failures.append({"reason": str(exc), "event_index": event["index"]})
                    continue
                expected = self.object_position(object_id, event["time"])
                if not _close(observed, expected):
                    failures.append({"reason": "Trusted object coordinate disagrees with independent attachment reconstruction",
                                     "event_index": event["index"], "object_id": object_id,
                                     "observed_xyz_m": observed, "reconstructed_xyz_m": expected})
        return {"status": "PASS" if not failures else "FAIL",
                "check_count": checks, "failures": failures}

    def motion_breakpoints(self):
        points = {self.trace_start, self.trace_end}
        points.update(row["time"] for row in self.events)
        for segments in self.moves.values():
            for segment in segments:
                points.update((segment.start_time, segment.end_time))
        return sorted(points)


def _complete_pair_inventory(spec):
    solids = list(spec["world"]["modeled_solids"])
    expected = {_pair_key((first, second)) for index, first in enumerate(solids)
                for second in solids[index + 1:]}
    declared_list = [tuple(pair) for pair in spec["world"].get("collision_pairs", [])]
    declared = {_pair_key(pair) for pair in declared_list}
    excluded_rows = spec["world"].get("excluded_pairs", [])
    excluded = {_pair_key(row["pair"] if isinstance(row, dict) else row) for row in excluded_rows}
    duplicates = len(declared_list) != len(declared)
    # Excluding a modeled-solid pair is a disclosed unsupported scope, not a
    # way to turn incomplete coverage into a global clear result.
    missing = sorted(expected - declared)
    extra = sorted((declared | excluded) - expected)
    overlap = sorted(declared & excluded)
    return {
        "status": "PASS" if not (duplicates or missing or extra or overlap or excluded) else "FAIL",
        "modeled_solids": solids,
        "expected_pair_count": len(expected),
        "declared_pair_count": len(declared),
        "excluded_pair_count": len(excluded),
        "duplicate_declared_pair": duplicates,
        "missing_pairs": [list(pair) for pair in missing],
        "extra_pairs": [list(pair) for pair in extra],
        "declared_and_excluded_overlap": [list(pair) for pair in overlap],
    }


def _robot_call_events(events, after_index, task_id):
    synchronous = {"signal", "clear_event"}
    return [row for row in events[after_index + 1:]
            if row.get("candidate_task_id") == task_id
            and (row.get("phase") == "start"
                 or (row.get("action") in synchronous and row.get("phase") in {"complete", "system"}))]


def _monotonic_departure(start, end, object_xyz):
    if math.sqrt(sum((after - before) ** 2 for before, after in zip(start, end))) <= TOLERANCE_M:
        return False
    for before, after, fixed in zip(start, end, object_xyz):
        initial = before - fixed
        delta = after - before
        if abs(initial) > TOLERANCE_M and initial * delta < -TOLERANCE_M:
            return False
    return True


def _permission_windows(model, declared_pairs):
    permissions = defaultdict(list)
    records = []
    allowed_keys = {_pair_key(row["pair"]) for row in model.spec["world"].get("contact_allowances", [])}

    for sequence in model.spec["world"].get("approach_sequences", []):
        arm, object_id = sequence["arm"], sequence["object_id"]
        pair = _pair_key((model.arms[arm], object_id))
        candidates = [segment for segment in model.moves[arm]
                      if segment.pose == sequence["interaction_pose"]]
        for move in candidates:
            start_expected = model.coordinates[sequence["start_pose"]]
            valid_start = _close(move.start_xyz, start_expected)
            terminal = (model.events[move.terminal_index]
                        if move.terminal_index is not None else None)
            next_calls = _robot_call_events(model.events, move.terminal_index or move.start_index,
                                            move.candidate_task_id)
            following = next_calls[0] if next_calls else None
            valid_next = bool(
                terminal is not None and terminal.get("phase") == "complete"
                and following is not None and following.get("action") == "grasp"
                and following.get("args", {}).get("arm") == arm
                and following.get("args", {}).get("object_id") == object_id
                and abs(following["time"] - move.end_time) <= TIME_TOLERANCE_S
            )
            object0 = model.object_position(object_id, move.start_time)
            object1 = model.object_position(object_id, move.end_time)
            interval = swept_aabb(move.start_xyz, move.end_xyz, object0, object1,
                                  model.sizes[model.arms[arm]], model.sizes[object_id])
            grasp_complete = None
            if following is not None:
                grasp_complete = next((row for row in model.events[following["index"] + 1:]
                                       if row.get("operation_id") == following.get("operation_id")
                                       and row.get("action") == "grasp" and row.get("phase") == "complete"), None)
            valid = pair in allowed_keys and valid_start and valid_next and interval is not None and grasp_complete is not None
            record = {
                "kind": "APPROACH_THEN_GRASP",
                "pair": list(pair),
                "move_operation_id": move.operation_id,
                "move_event_indexes": [move.start_index, move.terminal_index],
                "candidate_task_id": move.candidate_task_id,
                "declared_start_pose_match": valid_start,
                "same_task_next_matching_grasp_at_zero_time": valid_next,
                "contact_fraction_interval": interval,
                "status": "VALID" if valid else "INVALID",
            }
            if valid:
                contact_start = move.start_time + (move.end_time - move.start_time) * interval[0]
                window = [contact_start, grasp_complete["time"]]
                permissions[pair].append((window[0], window[1], "APPROACH_GRASP"))
                record["permission_time_interval_s"] = window
            else:
                model.permission_errors.append({"reason": "Invalid declared approach continuation",
                                                "details": record})
            records.append(record)

    for object_id, rows in model.attachments.items():
        for attachment in rows:
            pair = _pair_key((model.arms[attachment.arm], object_id))
            if pair not in allowed_keys:
                model.permission_errors.append({"reason": "Attachment pair lacks a public contact allowance",
                                                "pair": list(pair),
                                                "grasp_complete_index": attachment.grasp_complete_index})
                continue
            permissions[pair].append((attachment.grasp_start_time, attachment.released_at,
                                      "GRASP_ATTACHMENT_RELEASE"))
            records.append({"kind": "GRASP_ATTACHMENT_RELEASE", "pair": list(pair),
                            "time_interval_s": [attachment.grasp_start_time, attachment.released_at],
                            "attachment": attachment.record(), "status": "VALID"})
            if attachment.release_complete_index is None:
                continue
            following_moves = [segment for segment in model.moves[attachment.arm]
                               if segment.start_index > attachment.release_complete_index]
            departure = following_moves[0] if following_moves else None
            if departure is None or abs(departure.start_time - attachment.released_at) > TIME_TOLERANCE_S:
                records.append({"kind": "POST_RELEASE_DEPARTURE", "pair": list(pair),
                                "status": "NOT_EXERCISED_TRACE_END_OR_NO_IMMEDIATE_MOVE",
                                "release_time_s": attachment.released_at})
                continue
            object_xyz = model.object_position(object_id, attachment.released_at)
            monotonic = _monotonic_departure(departure.start_xyz, departure.end_xyz, object_xyz)
            interval = swept_aabb(departure.start_xyz, departure.end_xyz, object_xyz, object_xyz,
                                  model.sizes[model.arms[attachment.arm]], model.sizes[object_id])
            end_distance = box_signed_distance(
                departure.end_xyz, object_xyz,
                model.sizes[model.arms[attachment.arm]], model.sizes[object_id],
            )
            ends_clear = end_distance > TOLERANCE_M
            valid = (monotonic and interval is not None
                     and interval[0] <= TIME_TOLERANCE_S and ends_clear)
            departure_record = {"kind": "POST_RELEASE_DEPARTURE", "pair": list(pair),
                                "move_operation_id": departure.operation_id,
                                "monotonically_separating": monotonic,
                                "end_signed_distance_m": end_distance,
                                "ends_with_strict_positive_clearance": ends_clear,
                                "contact_fraction_interval": interval,
                                "status": "VALID" if valid else "INVALID"}
            if valid:
                clearance = departure.start_time + (departure.end_time - departure.start_time) * interval[1]
                permissions[pair].append((attachment.released_at, clearance,
                                          "POST_RELEASE_MONOTONIC_SEPARATION"))
                departure_record["permission_time_interval_s"] = [attachment.released_at, clearance]
            elif interval is not None:
                model.permission_errors.append({"reason": "Post-release contact does not follow a declared immediate monotonic departure",
                                                "details": departure_record})
            records.append(departure_record)

    merged = {}
    for pair in declared_pairs:
        key = _pair_key(pair)
        merged[key] = sorted(permissions.get(key, []))
    return merged, records


def _subtract_permissions(window, permissions):
    start, end = window
    if end - start <= TIME_TOLERANCE_S:
        covered = any(first - TIME_TOLERANCE_S <= start <= last + TIME_TOLERANCE_S
                      for first, last, _ in permissions)
        return [] if covered else [[start, end]]
    remaining = [[start, end]]
    for first, last, _ in permissions:
        updated = []
        for low, high in remaining:
            if last <= low + TIME_TOLERANCE_S or first >= high - TIME_TOLERANCE_S:
                updated.append([low, high])
                continue
            if first > low + TIME_TOLERANCE_S:
                updated.append([low, min(first, high)])
            if last < high - TIME_TOLERANCE_S:
                updated.append([max(last, low), high])
        remaining = updated
    return remaining


def _merge_contact_windows(rows):
    by_pair = defaultdict(list)
    for row in rows:
        by_pair[tuple(row["pair"])].append(row)
    merged = []
    for pair, values in by_pair.items():
        values.sort(key=lambda row: row["time_interval_s"])
        current = None
        for row in values:
            if current is None or row["time_interval_s"][0] > current["time_interval_s"][1] + TIME_TOLERANCE_S:
                if current is not None:
                    merged.append(current)
                current = {"pair": list(pair), "time_interval_s": list(row["time_interval_s"]),
                           "source_segments": list(row["source_segments"])}
            else:
                current["time_interval_s"][1] = max(current["time_interval_s"][1], row["time_interval_s"][1])
                current["source_segments"].extend(row["source_segments"])
        if current is not None:
            merged.append(current)
    return sorted(merged, key=lambda row: (row["time_interval_s"], row["pair"]))


class BulletChecker:
    def __init__(self, sizes):
        import pybullet as bullet

        self.bullet = bullet
        self.client = bullet.connect(bullet.DIRECT)
        self.ids = {}
        for body, half in sizes.items():
            shape = bullet.createCollisionShape(bullet.GEOM_BOX, halfExtents=half,
                                                physicsClientId=self.client)
            identifier = bullet.createMultiBody(baseMass=0, baseCollisionShapeIndex=shape,
                                                physicsClientId=self.client)
            bullet.changeDynamics(identifier, -1, collisionMargin=0,
                                  physicsClientId=self.client)
            self.ids[body] = identifier

    def distance(self, pair, positions):
        for body, xyz in positions.items():
            self.bullet.resetBasePositionAndOrientation(
                self.ids[body], xyz, [0, 0, 0, 1], physicsClientId=self.client
            )
        first, second = pair
        points = self.bullet.getClosestPoints(
            self.ids[first], self.ids[second], distance=10.0,
            physicsClientId=self.client,
        )
        if not points:
            raise GeometryInputError("Missing Bullet closest-point result inside bounded scene")
        return min(float(point[8]) for point in points)

    def close(self):
        self.bullet.disconnect(self.client)


def _distance_disagrees(analytic, observed, tolerance=TOLERANCE_M):
    if not math.isfinite(observed):
        return True
    if analytic > tolerance:
        return abs(analytic - observed) > tolerance
    if analytic < -tolerance:
        return observed >= tolerance
    return abs(observed) > tolerance


def _bullet_queries(model, pairs, breakpoints, contact_windows):
    requests = set()
    for at in breakpoints:
        for pair in pairs:
            requests.add((tuple(pair), round(at, 12), "EVENT_POINT"))
    for first, second in zip(breakpoints, breakpoints[1:]):
        if second <= first + TIME_TOLERANCE_S:
            continue
        for pair in pairs:
            for at, role in ((first, "SEGMENT_ENDPOINT"), ((first + second) / 2, "SEGMENT_MIDPOINT"),
                             (second, "SEGMENT_ENDPOINT")):
                requests.add((tuple(pair), round(at, 12), role))
    for row in contact_windows:
        low, high = row["time_interval_s"]
        for at, role in ((low, "CONTACT_BOUNDARY"), ((low + high) / 2, "CONTACT_WITNESS"),
                         (high, "CONTACT_BOUNDARY")):
            requests.add((tuple(row["pair"]), round(at, 12), role))
    queries, disagreements = [], []
    checker = BulletChecker(model.sizes)
    try:
        for pair_tuple, at, role in sorted(requests, key=lambda row: (row[1], row[0], row[2])):
            pair = list(pair_tuple)
            positions = {body: model.position(body, at) for body in model.solids}
            analytic = box_signed_distance(positions[pair[0]], positions[pair[1]],
                                           model.sizes[pair[0]], model.sizes[pair[1]])
            observed = checker.distance(pair, positions)
            row = {"pair": pair, "time_s": at, "role": role,
                   "analytic_signed_distance_m": analytic,
                   "bullet_distance_m": observed}
            if _distance_disagrees(analytic, observed):
                disagreements.append(row)
            queries.append(row)
    finally:
        checker.close()
    return {
        "status": "PASS" if not disagreements else "FAIL",
        "engine": "PyBullet " + importlib.metadata.version("pybullet"),
        "query_count": len(queries),
        "positive_or_boundary_query_count": sum(row["analytic_signed_distance_m"] <= TOLERANCE_M for row in queries),
        "negative_query_count": sum(row["analytic_signed_distance_m"] > TOLERANCE_M for row in queries),
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
        "queries": queries,
        "role": "Independent pointwise corroboration only; continuous negative coverage comes from swept AABB.",
    }


def evaluate_dynamic_evidence(spec: dict[str, Any], trusted_events, independent_replay=None):
    """Return proposition-specific dynamic contact evidence for one trace."""
    inventory = _complete_pair_inventory(spec)
    declared_pairs = [list(pair) for pair in spec["world"].get("collision_pairs", [])]
    model = TraceModel(spec, trusted_events)
    breakpoints = model.motion_breakpoints()
    permissions, permission_records = _permission_windows(model, declared_pairs)

    spans, raw_contacts = [], []
    pair_segment_counts = defaultdict(int)
    pair_point_counts = defaultdict(int)
    for segment_index, (start, end) in enumerate(zip(breakpoints, breakpoints[1:])):
        if end <= start + TIME_TOLERANCE_S:
            continue
        positions0 = {body: model.position(body, start) for body in model.solids}
        positions1 = {body: model.position(body, end) for body in model.solids}
        moving = [body for body in model.solids if not _close(positions0[body], positions1[body])]
        span = {"segment_id": f"segment_{segment_index:04d}",
                "time_interval_s": [start, end], "moving_bodies": moving,
                "positions_start_m": positions0, "positions_end_m": positions1}
        spans.append(span)
        for pair in declared_pairs:
            pair_segment_counts[_pair_key(pair)] += 1
            interval = swept_aabb(positions0[pair[0]], positions1[pair[0]],
                                  positions0[pair[1]], positions1[pair[1]],
                                  model.sizes[pair[0]], model.sizes[pair[1]])
            if interval is None:
                continue
            actual = [start + (end - start) * interval[0],
                      start + (end - start) * interval[1]]
            raw_contacts.append({"pair": list(_pair_key(pair)), "time_interval_s": actual,
                                 "source_segments": [span["segment_id"]]})
    # Explicit point checks cover initial state, same-time event boundaries and
    # the degenerate one-event/zero-duration trace that has no positive span.
    for point_index, at in enumerate(breakpoints):
        positions = {body: model.position(body, at) for body in model.solids}
        for pair in declared_pairs:
            pair_point_counts[_pair_key(pair)] += 1
            distance = box_signed_distance(positions[pair[0]], positions[pair[1]],
                                           model.sizes[pair[0]], model.sizes[pair[1]])
            if distance <= TOLERANCE_M:
                raw_contacts.append({"pair": list(_pair_key(pair)), "time_interval_s": [at, at],
                                     "source_segments": [f"point_{point_index:04d}"]})
    contact_windows = _merge_contact_windows(raw_contacts)

    findings, allowed_contacts = [], []
    for window in contact_windows:
        pair = tuple(window["pair"])
        uncovered = _subtract_permissions(window["time_interval_s"], permissions.get(pair, []))
        record = dict(window)
        record["permission_windows"] = [
            {"time_interval_s": [first, last], "kind": kind}
            for first, last, kind in permissions.get(pair, [])
        ]
        record["uncovered_time_intervals_s"] = uncovered
        record["permission_status"] = "ALLOWED_BY_PUBLISHED_LIFECYCLE" if not uncovered else "FORBIDDEN_OR_PARTIALLY_FORBIDDEN"
        if uncovered:
            for interval in uncovered:
                findings.append({"code": "FORBIDDEN_DECLARED_PAIR_CONTACT",
                                 "pair": list(pair), "time_interval_s": interval,
                                 "source_contact_window_s": window["time_interval_s"],
                                 "source_segments": window["source_segments"]})
        else:
            allowed_contacts.append(record)
        window.update(record)

    # Initial overlap is forbidden independently of any t=0 grasp/permission.
    initial_positions = {body: model.position(body, model.trace_start) for body in model.solids}
    initial_overlap_pairs = []
    for pair in declared_pairs:
        if box_signed_distance(initial_positions[pair[0]], initial_positions[pair[1]],
                               model.sizes[pair[0]], model.sizes[pair[1]]) <= TOLERANCE_M:
            initial_overlap_pairs.append(list(_pair_key(pair)))
            findings.append({"code": "FORBIDDEN_INITIAL_OVERLAP",
                             "pair": list(_pair_key(pair)),
                             "time_interval_s": [model.trace_start, model.trace_start],
                             "source_segments": ["INITIAL_STATE_POINT"]})

    bullet = _bullet_queries(model, declared_pairs, breakpoints, contact_windows)
    trace_complete = bool(model.events) and model.events[-1].get("phase") == "complete" \
        and model.events[-1].get("action") == "run_return" \
        and model.events[-1].get("pending_task_count") == 0
    replay_errors = []
    if independent_replay is not None:
        replay_errors = [row for row in independent_replay.get("evidence_errors", [])
                         if row.get("reason") != "No complete joined trace"]
    reconstruction_failures = list(model.errors) + list(model.reconstruction_checks["failures"])
    if inventory["status"] != "PASS":
        reconstruction_failures.append({"reason": "Incomplete or invalid modeled-solid pair inventory",
                                        "inventory": inventory})
    if bullet["status"] != "PASS":
        status = "GEOMETRY_DISAGREEMENT"
    elif reconstruction_failures:
        status = "INCONCLUSIVE_EVENT_OR_RECONSTRUCTION_ERROR"
    elif findings:
        status = "VIOLATIONS" if trace_complete else "VIOLATIONS_ON_OBSERVED_PREFIX"
    elif replay_errors:
        status = "INCONCLUSIVE_EVENT_OR_RECONSTRUCTION_ERROR"
    elif not trace_complete:
        status = "INCONCLUSIVE_INCOMPLETE_TRACE"
    else:
        status = "NO_FORBIDDEN_CONTACT_IN_DECLARED_FIXED_AABB_TRANSLATIONS"

    query_counts = defaultdict(int)
    for row in bullet["queries"]:
        query_counts[_pair_key(row["pair"])] += 1
    pair_coverage = {
        "status": "PASS" if inventory["status"] == "PASS"
        and all(pair_segment_counts[_pair_key(pair)] == len(spans)
                and pair_point_counts[_pair_key(pair)] == len(breakpoints)
                for pair in declared_pairs) else "FAIL",
        "inventory": inventory,
        "time_segment_count": len(spans),
        "pairs": [
            {"pair": list(_pair_key(pair)),
             "evaluated_time_segments": pair_segment_counts[_pair_key(pair)],
             "expected_time_segments": len(spans),
             "evaluated_event_points": pair_point_counts[_pair_key(pair)],
             "expected_event_points": len(breakpoints),
             "contact_window_count": sum(tuple(row["pair"]) == _pair_key(pair) for row in contact_windows),
             "bullet_query_count": query_counts[_pair_key(pair)]}
            for pair in declared_pairs
        ],
        "unmodeled": [list(pair) for pair in sorted({_pair_key(row["pair"] if isinstance(row, dict) else row)
                                                      for row in spec["world"].get("excluded_pairs", [])})],
    }

    return {
        "schema_version": 1,
        "profile": PROFILE,
        "task_id": spec["task_id"],
        "axis_id": spec["axis_id"],
        "variant": spec["variant"],
        "status": status,
        "trace_complete": trace_complete,
        "pair_coverage": pair_coverage,
        "motion_segments": spans,
        "move_reconstruction": [segment.record() for arm in sorted(model.moves)
                                for segment in model.moves[arm]],
        "attachment_reconstruction": [attachment.record() for object_id in sorted(model.attachments)
                                      for attachment in model.attachments[object_id]],
        "contact_windows": contact_windows,
        "allowed_contact_windows": allowed_contacts,
        "permission_windows": permission_records,
        "permission_errors": model.permission_errors,
        "findings": findings,
        "initial_overlap_pairs": initial_overlap_pairs,
        "reconstruction_checks": {
            "status": "PASS" if not reconstruction_failures else "FAIL",
            "snapshot_checks": model.reconstruction_checks,
            "failures": reconstruction_failures,
            "independent_replay_errors": replay_errors,
            "replay_gate_semantics": "Non-completeness is handled by prefix status. Other replay errors block only a negative conclusion; an independently reconstructed forbidden contact is retained unless reconstruction or Bullet consistency fails.",
        },
        "bullet_consistency": bullet,
        "continuous_method": "Closed-form swept interval intersection for every declared unordered pair on every fixed-orientation affine time segment, including static bodies and simultaneous moves.",
        "logical_support_treatment": "NOT_A_GEOMETRY_BODY; no support shape or stability was invented.",
        "scope": "Declared fixed-orientation rigid AABBs and the observed trusted trace only; no rotation, articulated links, forces, friction, flexible bodies, grasp force, exhaustive scheduling or whole-robot safety.",
        "safety_label": None,
    }
