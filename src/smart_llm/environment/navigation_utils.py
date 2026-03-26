#!/usr/bin/env python3
"""
Navigation Utilities for AI2-THOR
- 목표: 객체까지 안정적으로 이동하되, primitive action 단위로 진행 상황을 내보낸다.
- 메커니즘: 상호작용 가능한 pose 검색 → 충돌 회피 가능한 pose 선택 → 경로 추적 + 회전/후진 기반 복구
"""

from __future__ import annotations

import math
from typing import Any, Dict, Generator, List, Sequence, Tuple

from smart_llm.models import ActionResult


INTERACTABLE_ROTATIONS = list(range(0, 360, 30))
INTERACTABLE_HORIZONS = [-30, 0, 30, 60]
ARRIVAL_TOLERANCE = 0.25
WAYPOINT_TOLERANCE = 0.15
AGENT_CLEARANCE = 0.75
TIGHT_INTERACTION_AGENT_CLEARANCE = 0.5
FALLBACK_POSE_RADIUS = 2.25
STRICT_DISTANCE_GEOMETRY_MARGIN = 0.6


def calculate_distance(pos1, pos2):
    """두 위치 간 2D 거리"""
    return math.sqrt((pos1['x'] - pos2['x'])**2 + (pos1['z'] - pos2['z'])**2)


def calculate_angle(from_pos, to_pos):
    """목표 방향의 각도 (degrees)"""
    dx = to_pos['x'] - from_pos['x']
    dz = to_pos['z'] - from_pos['z']
    return math.degrees(math.atan2(dx, dz))


def normalize_angle(angle):
    """각도를 -180~180 범위로 정규화"""
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


def path_length(corners: Sequence[Dict[str, float]]) -> float:
    if len(corners) < 2:
        return 0.0
    return sum(calculate_distance(corners[idx - 1], corners[idx]) for idx in range(1, len(corners)))


def _get_metadata(controller, agent_id):
    if agent_id is not None:
        return controller.last_event.events[agent_id].metadata
    return controller.last_event.metadata


def _event_metadata(event, agent_id):
    if agent_id is not None and hasattr(event, "events"):
        events = getattr(event, "events", None) or []
        if 0 <= agent_id < len(events):
            return events[agent_id].metadata
    return getattr(event, "metadata", {}) or {}


def _last_action_success(event, agent_id) -> bool:
    return bool(_event_metadata(event, agent_id).get("lastActionSuccess"))


def _action_return(event, agent_id):
    return _event_metadata(event, agent_id).get("actionReturn")


def _step_kwargs(agent_id):
    return {"agentId": agent_id} if agent_id is not None else {}


def _capture(capture_callback, event=None):
    try:
        capture_callback(event)
    except TypeError:
        capture_callback()


def _other_agent_positions(controller, agent_id) -> List[Dict[str, float]]:
    if agent_id is None or not hasattr(controller.last_event, "events"):
        return []

    positions = []
    for idx, event in enumerate(controller.last_event.events):
        if idx == agent_id:
            continue
        positions.append(event.metadata["agent"]["position"])
    return positions


def _min_clearance(position: Dict[str, float], blockers: Sequence[Dict[str, float]]) -> float:
    if not blockers:
        return 999.0
    return min(calculate_distance(position, blocker) for blocker in blockers)


def _dedupe_poses(poses: Sequence[Dict[str, float]], current_rotation: float, current_horizon: float) -> List[Dict[str, float]]:
    best_by_position: Dict[Tuple[float, float], Tuple[Tuple[float, float, int], Dict[str, float]]] = {}

    for pose in poses:
        key = (round(pose["x"], 2), round(pose["z"], 2))
        score = (
            abs(normalize_angle(float(pose.get("rotation", 0)) - current_rotation)),
            abs(float(pose.get("horizon", 0)) - current_horizon),
            0 if pose.get("standing", True) else 1,
        )
        existing = best_by_position.get(key)
        if existing is None or score < existing[0]:
            best_by_position[key] = (score, pose)

    return [row[1] for row in best_by_position.values()]


def _pose_distance_to_object(pose: Dict[str, float], obj_pos: Dict[str, float]) -> float:
    return calculate_distance(
        obj_pos,
        {"x": float(pose["x"]), "y": float(pose["y"]), "z": float(pose["z"])},
    )


def _should_enforce_strict_distance(
    candidate_poses: Sequence[Dict[str, float]],
    obj_pos: Dict[str, float],
    max_distance: float | None,
) -> bool:
    if max_distance is None or not candidate_poses:
        return False

    interactable_poses = [
        pose
        for pose in candidate_poses
        if str(pose.get("pose_source", "interactable")) == "interactable"
    ]
    poses_for_check = interactable_poses or list(candidate_poses)
    closest_pose_distance = min(_pose_distance_to_object(pose, obj_pos) for pose in poses_for_check)
    return closest_pose_distance <= max_distance + STRICT_DISTANCE_GEOMETRY_MARGIN


def _query_interactable_poses(controller, agent_id, obj_id, positions):
    step_kwargs = _step_kwargs(agent_id)
    event = controller.step(
        action="GetInteractablePoses",
        objectId=obj_id,
        positions=positions,
        rotations=INTERACTABLE_ROTATIONS,
        horizons=INTERACTABLE_HORIZONS,
        standings=[True],
        **step_kwargs,
    )
    if not _last_action_success(event, agent_id):
        return []
    return _action_return(event, agent_id) or []


def _candidate_poses(
    controller,
    agent_id,
    obj_id,
    obj_pos,
    reachable_positions,
    agent_clearance: float = AGENT_CLEARANCE,
) -> List[Dict[str, float]]:
    metadata = _get_metadata(controller, agent_id)
    current_rotation = metadata["agent"]["rotation"]["y"]
    current_horizon = metadata["agent"].get("cameraHorizon", 0)
    other_positions = _other_agent_positions(controller, agent_id)

    filtered_positions = [
        pos for pos in reachable_positions if _min_clearance(pos, other_positions) >= agent_clearance
    ]
    poses = _query_interactable_poses(
        controller,
        agent_id,
        obj_id,
        filtered_positions or reachable_positions,
    )
    if not poses and filtered_positions:
        poses = _query_interactable_poses(controller, agent_id, obj_id, reachable_positions)
    fallback_poses = _fallback_candidate_poses(
        obj_pos=obj_pos,
        reachable_positions=filtered_positions or reachable_positions,
        current_rotation=current_rotation,
        current_horizon=current_horizon,
    )
    if not poses:
        return fallback_poses

    unique_poses = _dedupe_poses(poses, current_rotation, current_horizon)
    unique_poses.sort(
        key=lambda pose: _pose_distance_to_object(pose, obj_pos)
    )
    scored = []
    step_kwargs = _step_kwargs(agent_id)

    for pose in unique_poses[:48]:
        pose = dict(pose)
        pose["pose_source"] = "interactable"
        target_pos = {"x": pose["x"], "y": pose["y"], "z": pose["z"]}
        path_event = controller.step(action="GetShortestPathToPoint", target=target_pos, **step_kwargs)
        if not _last_action_success(path_event, agent_id):
            continue
        corners = (_action_return(path_event, agent_id) or {}).get("corners") or []
        scored.append(
            (
                calculate_distance(obj_pos, target_pos),
                path_length(corners),
                -_min_clearance(target_pos, other_positions),
                pose,
            )
        )

    scored.sort(key=lambda row: row[:3])
    ranked = [row[3] for row in scored]
    if fallback_poses:
        ranked.extend(
            pose
            for pose in fallback_poses
            if not any(
                round(pose["x"], 2) == round(existing["x"], 2)
                and round(pose["z"], 2) == round(existing["z"], 2)
                for existing in ranked
            )
        )
    return ranked


def _fallback_candidate_poses(
    obj_pos: Dict[str, float],
    reachable_positions: Sequence[Dict[str, float]],
    current_rotation: float,
    current_horizon: float,
) -> List[Dict[str, float]]:
    if not reachable_positions:
        return []

    nearby_positions = [
        pos
        for pos in reachable_positions
        if calculate_distance(pos, obj_pos) <= FALLBACK_POSE_RADIUS
    ]
    candidate_positions = nearby_positions or sorted(
        reachable_positions,
        key=lambda pos: calculate_distance(pos, obj_pos),
    )[:12]

    poses: List[Dict[str, float]] = []
    for pos in candidate_positions[:12]:
        poses.append(
            {
                "x": float(pos["x"]),
                "y": float(pos["y"]),
                "z": float(pos["z"]),
                "rotation": float(calculate_angle(pos, obj_pos)),
                "horizon": 0.0,
                "standing": True,
                "pose_source": "fallback",
            }
        )

    return _dedupe_poses(poses, current_rotation, current_horizon)


def _progress(message: str, transitions: int = 1) -> ActionResult:
    return ActionResult(success=True, status="progress", message=message, transitions=transitions)


def _failure(message: str, transitions: int = 0) -> ActionResult:
    return ActionResult(success=False, status="failure", message=message, transitions=transitions)


def _align_to_pose_iter(
    controller,
    agent_id,
    target_rotation,
    target_horizon,
    capture_callback,
) -> Generator[ActionResult, None, None]:
    step_kwargs = _step_kwargs(agent_id)
    metadata = _get_metadata(controller, agent_id)
    current_rotation = metadata["agent"]["rotation"]["y"]

    if target_rotation is not None:
        angle_diff = normalize_angle(float(target_rotation) - current_rotation)
        if abs(angle_diff) > 5:
            rotate_action = "RotateRight" if angle_diff > 0 else "RotateLeft"
            event = controller.step(action=rotate_action, degrees=abs(angle_diff), **step_kwargs)
            _capture(capture_callback, event)
            yield _progress(f"align:{rotate_action.lower()}")

    if target_horizon is not None:
        metadata = _get_metadata(controller, agent_id)
        current_horizon = metadata["agent"].get("cameraHorizon", 0)
        horizon_diff = float(target_horizon) - current_horizon
        if abs(horizon_diff) > 1:
            look_action = "LookDown" if horizon_diff > 0 else "LookUp"
            event = controller.step(action=look_action, degrees=abs(horizon_diff), **step_kwargs)
            _capture(capture_callback, event)
            yield _progress(f"align:{look_action.lower()}")


def _visibility_sweep_iter(controller, agent_id, object_type, capture_callback) -> Generator[ActionResult, None, bool]:
    metadata = _get_metadata(controller, agent_id)
    step_kwargs = _step_kwargs(agent_id)

    print("  👀 수직 탐색")
    if check_visible(metadata, object_type):
        print("  ✓ 발견 (정면)")
        return True

    event = controller.step(action="LookDown", degrees=30, **step_kwargs)
    _capture(capture_callback, event)
    yield _progress("visibility:look_down")
    if check_visible(_get_metadata(controller, agent_id), object_type):
        print("  ✓ 발견 (아래)")
        return True

    event = controller.step(action="LookUp", degrees=60, **step_kwargs)
    _capture(capture_callback, event)
    yield _progress("visibility:look_up")
    if check_visible(_get_metadata(controller, agent_id), object_type):
        print("  ✓ 발견 (위)")
        return True

    event = controller.step(action="LookDown", degrees=30, **step_kwargs)
    _capture(capture_callback, event)
    yield _progress("visibility:look_down_reset")
    return False


def _recovery_plan(angle_diff: float, stuck_streak: int) -> List[Tuple[str, Dict[str, float]]]:
    primary_turn = "RotateRight" if angle_diff >= 0 else "RotateLeft"
    secondary_turn = "RotateLeft" if angle_diff >= 0 else "RotateRight"

    if stuck_streak == 1:
        return [(primary_turn, {"degrees": 25}), ("MoveAhead", {"moveMagnitude": 0.15})]
    if stuck_streak == 2:
        return [(secondary_turn, {"degrees": 40}), ("MoveAhead", {"moveMagnitude": 0.15})]
    if stuck_streak == 3:
        return [("MoveBack", {"moveMagnitude": 0.15}), (primary_turn, {"degrees": 45}), ("MoveAhead", {"moveMagnitude": 0.15})]
    if stuck_streak == 4:
        return [("MoveBack", {"moveMagnitude": 0.2}), (secondary_turn, {"degrees": 55}), ("MoveAhead", {"moveMagnitude": 0.15})]
    return []


def _recovery_iter(
    controller,
    agent_id,
    angle_diff,
    stuck_streak,
    capture_callback,
) -> Generator[ActionResult, None, bool]:
    step_kwargs = _step_kwargs(agent_id)
    plan = _recovery_plan(angle_diff, stuck_streak)
    if not plan:
        return False

    progressed = False
    for action, params in plan:
        event = controller.step(action=action, **params, **step_kwargs)
        _capture(capture_callback, event)
        ok = _last_action_success(event, agent_id)
        progressed = progressed or ok
        suffix = "ok" if ok else "blocked"
        yield _progress(f"recovery:{action.lower()}:{suffix}")

    return progressed


def _teleport_pose_kwargs(pose: Dict[str, Any]) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}

    if "position" in pose:
        kwargs["position"] = dict(pose["position"])
    else:
        kwargs["x"] = float(pose["x"])
        kwargs["y"] = float(pose["y"])
        kwargs["z"] = float(pose["z"])

    rotation = pose.get("rotation")
    if rotation is not None:
        kwargs["rotation"] = float(rotation) if not isinstance(rotation, dict) else dict(rotation)

    horizon = pose.get("horizon")
    if horizon is not None:
        kwargs["horizon"] = float(horizon)

    standing = pose.get("standing")
    if standing is not None:
        kwargs["standing"] = bool(standing)

    return kwargs


def try_reach_pose_iter(
    controller,
    agent_id,
    pose,
    capture_callback,
    max_steps=120,
) -> Generator[ActionResult, None, bool]:
    step_kwargs = _step_kwargs(agent_id)
    teleport_event = controller.step(
        action="TeleportFull",
        **_teleport_pose_kwargs(pose),
        **step_kwargs,
    )
    _capture(capture_callback, teleport_event)
    if _last_action_success(teleport_event, agent_id):
        yield _progress("move:teleportfull")
        print("    ✓ 도착 (TeleportFull)")
        return True

    yield _progress("move:teleportfull:blocked")
    return (
        yield from try_reach_position_iter(
            controller,
            agent_id,
            {"x": pose["x"], "y": pose["y"], "z": pose["z"]},
            capture_callback,
            max_steps=max_steps,
            target_rotation=pose.get("rotation"),
            target_horizon=pose.get("horizon"),
        )
    )


def _within_interaction_distance(metadata, object_id, max_distance: float | None) -> bool:
    if max_distance is None:
        return True

    for obj in metadata.get("objects", []):
        if obj.get("objectId") != object_id or not obj.get("visible"):
            continue
        distance = obj.get("distance")
        if distance is None:
            return True
        return float(distance) <= max_distance
    return False


def navigate_to_object_iter(
    controller,
    agent_id,
    object_type,
    capture_callback,
    max_distance: float | None = None,
    agent_clearance: float = AGENT_CLEARANCE,
    strict_max_distance: bool = False,
) -> Generator[ActionResult, None, bool]:
    """
    객체까지 이동하여 상호작용 준비.
    Primitive action마다 ActionResult를 yield하므로 상위 executor가 다른 agent와 interleave할 수 있다.
    """
    print(f"\n🎯 객체 네비게이션: {object_type}")

    get_metadata = lambda: _get_metadata(controller, agent_id)

    all_objects = get_metadata()['objects']
    target_objects = [obj for obj in all_objects if obj['objectType'] == object_type]

    if not target_objects:
        print(f"  ❌ {object_type} 없음")
        yield _failure(f"navigate:{object_type}:missing")
        return False

    current_pos = get_metadata()['agent']['position']
    target_obj = min(target_objects, key=lambda obj: calculate_distance(current_pos, obj['position']))
    obj_id = target_obj['objectId']
    obj_pos = target_obj['position']
    print(f"  📍 목표: {obj_id}")

    reach_event = controller.step(action='GetReachablePositions', **_step_kwargs(agent_id))
    if not _last_action_success(reach_event, agent_id):
        print(f"  ❌ GetReachablePositions 실패")
        yield _failure(f"navigate:{object_type}:reachable_positions_failed")
        return False

    reachable_positions = _action_return(reach_event, agent_id) or []

    candidate_poses = _candidate_poses(
        controller,
        agent_id,
        obj_id,
        obj_pos,
        reachable_positions,
        agent_clearance=agent_clearance,
    )
    if not candidate_poses:
        print(f"  ❌ 상호작용 가능한 pose를 찾지 못함")
        yield _failure(f"navigate:{object_type}:no_interactable_pose")
        return False

    effective_strict_max_distance = strict_max_distance and _should_enforce_strict_distance(
        candidate_poses,
        obj_pos,
        max_distance,
    )

    for i, pose in enumerate(candidate_poses[:5]):
        print(f"  📍 시도 {i+1}/{min(len(candidate_poses), 5)}: ({pose['x']:.2f}, {pose['z']:.2f})")
        reached = yield from try_reach_pose_iter(
            controller,
            agent_id,
            pose,
            capture_callback,
            max_steps=120,
        )
        if not reached:
            print(f"  ⚠️ 시도 {i+1} 실패, 다음 목표 시도")
            continue

        visible = yield from _visibility_sweep_iter(controller, agent_id, object_type, capture_callback)
        pose_source = str(pose.get("pose_source", "interactable"))
        within_distance = _within_interaction_distance(get_metadata(), obj_id, max_distance)
        if visible and (
            max_distance is None
            or within_distance
            or (pose_source == "interactable" and not effective_strict_max_distance)
        ):
            return True
        if visible and max_distance is not None:
            actual_obj = next((obj for obj in get_metadata()["objects"] if obj.get("objectId") == obj_id), None)
            actual_distance = actual_obj.get("distance") if actual_obj is not None else None
            if actual_distance is not None:
                print(f"  ⚠️ 상호작용 거리 초과 ({float(actual_distance):.2f}m > {max_distance:.2f}m)")
            else:
                print(f"  ⚠️ 상호작용 거리 초과")

        print(f"  ⚠️ 시도 {i+1} 실패, 다음 목표 시도")

    print(f"  ❌ 모든 목표 위치 도달 실패")
    yield _failure(f"navigate:{object_type}:unreachable")
    return False


def navigate_to_object(
    controller,
    agent_id,
    object_type,
    capture_callback,
    max_distance: float | None = None,
    agent_clearance: float = AGENT_CLEARANCE,
    strict_max_distance: bool = False,
):
    success = True
    for result in navigate_to_object_iter(
        controller,
        agent_id,
        object_type,
        capture_callback,
        max_distance=max_distance,
        agent_clearance=agent_clearance,
        strict_max_distance=strict_max_distance,
    ):
        success = result.success
        if not result.success:
            return False
    return success


def try_reach_position_iter(
    controller,
    agent_id,
    target_pos,
    capture_callback,
    max_steps=120,
    target_rotation=None,
    target_horizon=None,
) -> Generator[ActionResult, None, bool]:
    get_metadata = lambda: _get_metadata(controller, agent_id)
    step_kwargs = _step_kwargs(agent_id)

    initial_pos = get_metadata()['agent']['position']
    initial_dist = calculate_distance(initial_pos, target_pos)
    print(f"    🚶 이동 시작: {initial_dist:.2f}m")

    path = []
    path_index = 0
    steps = 0
    stuck_streak = 0

    while steps < max_steps:
        current_pos = get_metadata()['agent']['position']
        final_dist = calculate_distance(current_pos, target_pos)
        if final_dist <= ARRIVAL_TOLERANCE:
            break

        if not path or path_index >= len(path):
            path_event = controller.step(action='GetShortestPathToPoint', target=target_pos, **step_kwargs)
            if not _last_action_success(path_event, agent_id):
                return False

            path = (_action_return(path_event, agent_id) or {}).get('corners') or []
            if not path:
                return False

            path_index = 1 if len(path) > 1 else 0
            print(f"    🗺️ 경로: {len(path)}개 웨이포인트")

        if path_index >= len(path):
            continue

        waypoint = path[path_index]
        waypoint_dist = calculate_distance(current_pos, waypoint)
        if waypoint_dist <= WAYPOINT_TOLERANCE:
            path_index += 1
            continue

        current_rot = get_metadata()['agent']['rotation']['y']
        target_angle = calculate_angle(current_pos, waypoint)
        angle_diff = normalize_angle(target_angle - current_rot)

        if abs(angle_diff) > 12:
            rotate_action = 'RotateRight' if angle_diff > 0 else 'RotateLeft'
            event = controller.step(action=rotate_action, degrees=min(20, abs(angle_diff)), **step_kwargs)
            _capture(capture_callback, event)
            steps += 1
            yield _progress(f"move:{rotate_action.lower()}")
            continue

        move_magnitude = min(0.25, max(0.1, min(final_dist, waypoint_dist)))
        move_result = controller.step(action='MoveAhead', moveMagnitude=move_magnitude, **step_kwargs)
        _capture(capture_callback, move_result)
        steps += 1

        new_pos = get_metadata()['agent']['position']
        moved_dist = calculate_distance(current_pos, new_pos)
        new_final_dist = calculate_distance(new_pos, target_pos)

        if _last_action_success(move_result, agent_id) and moved_dist > 0.02 and new_final_dist < final_dist:
            stuck_streak = 0
            yield _progress("move:ahead")
            continue

        stuck_streak += 1
        path = []
        path_index = 0
        yield _progress(f"move:blocked:stuck={stuck_streak}")

        recovered = yield from _recovery_iter(
            controller,
            agent_id,
            angle_diff,
            stuck_streak,
            capture_callback,
        )
        steps += len(_recovery_plan(angle_diff, stuck_streak))
        if not recovered and stuck_streak >= 4:
            return False

    final_pos = get_metadata()['agent']['position']
    final_dist = calculate_distance(final_pos, target_pos)

    if final_dist <= ARRIVAL_TOLERANCE:
        yield from _align_to_pose_iter(controller, agent_id, target_rotation, target_horizon, capture_callback)
        print(f"    ✓ 도착 (거리 {final_dist:.2f}m)")
        return True

    print(f"    ⚠️ 목표에서 멀리 떨어짐 (거리 {final_dist:.2f}m)")
    return False


def check_visible(metadata, object_type):
    """객체가 보이는지 확인"""
    return any(obj['visible'] and obj['objectType'] == object_type 
               for obj in metadata['objects'])
