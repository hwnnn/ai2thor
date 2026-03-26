from __future__ import annotations

import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smart_llm.environment.navigation_utils import TIGHT_INTERACTION_AGENT_CLEARANCE, navigate_to_object


def _agent_metadata(*, position, objects, action_return=None, success=True):
    return {
        "agent": {
            "position": dict(position),
            "rotation": {"y": 0.0},
            "cameraHorizon": 0.0,
        },
        "objects": [dict(obj) for obj in objects],
        "lastActionSuccess": success,
        "actionReturn": action_return,
    }


def _event(agent_metadatas, *, top_success=True, top_action_return=None):
    return SimpleNamespace(
        metadata={
            "lastActionSuccess": top_success,
            "actionReturn": top_action_return,
        },
        events=[SimpleNamespace(metadata=meta) for meta in agent_metadatas],
    )


class FakeMultiAgentController:
    def __init__(self):
        self.actions = []
        self._target_object = {
            "objectId": "Bread|+00.50|+00.90|+00.30",
            "objectType": "Bread",
            "position": {"x": 0.5, "y": 0.9, "z": 0.3},
            "visible": False,
            "distance": 2.0,
        }
        self._agent_positions = [
            {"x": -1.5, "y": 0.9, "z": -1.5},
            {"x": -1.0, "y": 0.9, "z": -1.0},
        ]
        self.last_event = self._current_event()

    def _current_event(self):
        agent0_objects = [dict(self._target_object, visible=False, distance=3.0)]
        agent1_objects = [dict(self._target_object)]
        agent1_objects[0]["distance"] = 2.0
        return _event(
            [
                _agent_metadata(position=self._agent_positions[0], objects=agent0_objects),
                _agent_metadata(position=self._agent_positions[1], objects=agent1_objects),
            ],
            top_success=True,
            top_action_return=[],
        )

    def _query_event(self, agent_id, action_return):
        metadatas = []
        for idx, position in enumerate(self._agent_positions):
            objects = [dict(self._target_object)]
            objects[0]["visible"] = idx == agent_id
            objects[0]["distance"] = 1.0 if idx == agent_id else 3.0
            metadatas.append(
                _agent_metadata(
                    position=position,
                    objects=objects,
                    action_return=action_return if idx == agent_id else [],
                    success=True,
                )
            )
        return _event(metadatas, top_success=True, top_action_return=[])

    def step(self, action, agentId=None, **kwargs):
        self.actions.append((action, agentId, kwargs))
        if action == "GetReachablePositions":
            event = self._query_event(
                agentId,
                [{"x": -0.75, "y": 0.9, "z": -0.5}],
            )
        elif action == "GetInteractablePoses":
            event = self._query_event(
                agentId,
                [{"x": -0.75, "y": 0.9, "z": -0.5, "rotation": 0.0, "horizon": 0.0, "standing": True}],
            )
        elif action == "GetShortestPathToPoint":
            current = dict(self._agent_positions[agentId])
            target = dict(kwargs["target"])
            event = self._query_event(agentId, {"corners": [current, target]})
        elif action == "TeleportFull":
            self._agent_positions[agentId] = {"x": kwargs["x"], "y": kwargs["y"], "z": kwargs["z"]}
            metadatas = []
            for idx, position in enumerate(self._agent_positions):
                distance = 1.0 if idx == agentId else 3.0
                objects = [dict(self._target_object, visible=idx == agentId, distance=distance)]
                metadatas.append(_agent_metadata(position=position, objects=objects, success=True))
            event = _event(metadatas, top_success=True, top_action_return=[])
        else:
            raise AssertionError(f"Unexpected action: {action}")

        self.last_event = event
        return event


class FakeLongDistanceInteractablePoseController(FakeMultiAgentController):
    def _query_event(self, agent_id, action_return):
        metadatas = []
        for idx, position in enumerate(self._agent_positions):
            objects = [dict(self._target_object)]
            objects[0]["visible"] = idx == agent_id
            objects[0]["distance"] = 1.39 if idx == agent_id else 3.0
            metadatas.append(
                _agent_metadata(
                    position=position,
                    objects=objects,
                    action_return=action_return if idx == agent_id else [],
                    success=True,
                )
            )
        return _event(metadatas, top_success=True, top_action_return=[])


class FakeFallbackPoseController(FakeMultiAgentController):
    def step(self, action, agentId=None, **kwargs):
        self.actions.append((action, agentId, kwargs))
        if action == "GetReachablePositions":
            event = self._query_event(
                agentId,
                [
                    {"x": -0.75, "y": 0.9, "z": -0.5},
                    {"x": -0.50, "y": 0.9, "z": -0.25},
                ],
            )
        elif action == "GetInteractablePoses":
            event = self._query_event(agentId, [])
        elif action == "GetShortestPathToPoint":
            current = dict(self._agent_positions[agentId])
            target = dict(kwargs["target"])
            event = self._query_event(agentId, {"corners": [current, target]})
        elif action == "TeleportFull":
            self._agent_positions[agentId] = {"x": kwargs["x"], "y": kwargs["y"], "z": kwargs["z"]}
            metadatas = []
            for idx, position in enumerate(self._agent_positions):
                distance = 1.0 if idx == agentId else 3.0
                objects = [dict(self._target_object, visible=idx == agentId, distance=distance)]
                metadatas.append(_agent_metadata(position=position, objects=objects, success=True))
            event = _event(metadatas, top_success=True, top_action_return=[])
        else:
            raise AssertionError(f"Unexpected action: {action}")

        self.last_event = event
        return event


class FakePoseRankingController(FakeMultiAgentController):
    def __init__(self):
        super().__init__()
        self._target_object = {
            "objectId": "Bread|0",
            "objectType": "Bread",
            "position": {"x": 0.0, "y": 0.9, "z": 0.0},
            "visible": False,
            "distance": 2.0,
        }
        self._agent_positions = [{"x": -2.0, "y": 0.9, "z": -2.0}, {"x": -1.0, "y": 0.9, "z": -1.0}]
        self.last_event = self._current_event()

    def step(self, action, agentId=None, **kwargs):
        self.actions.append((action, agentId, kwargs))
        near_pose = {"x": -1.0, "y": 0.9, "z": 0.0, "rotation": 90.0, "horizon": 0.0, "standing": True}
        far_pose = {"x": -1.0, "y": 0.9, "z": -1.0, "rotation": 45.0, "horizon": 0.0, "standing": True}

        if action == "GetReachablePositions":
            event = self._query_event(agentId, [near_pose, far_pose])
        elif action == "GetInteractablePoses":
            event = self._query_event(agentId, [near_pose, far_pose])
        elif action == "GetShortestPathToPoint":
            target = dict(kwargs["target"])
            if round(target["x"], 2) == -1.0 and round(target["z"], 2) == 0.0:
                corners = [
                    dict(self._agent_positions[agentId]),
                    {"x": -1.5, "y": 0.9, "z": -1.0},
                    target,
                ]
            else:
                corners = [dict(self._agent_positions[agentId]), target]
            event = self._query_event(agentId, {"corners": corners})
        elif action == "TeleportFull":
            self._agent_positions[agentId] = {"x": kwargs["x"], "y": kwargs["y"], "z": kwargs["z"]}
            metadatas = []
            for idx, position in enumerate(self._agent_positions):
                visible = idx == agentId
                distance = 0.55 if visible and round(position["z"], 2) == 0.0 else 1.35
                objects = [dict(self._target_object, visible=visible, distance=distance)]
                metadatas.append(_agent_metadata(position=position, objects=objects, success=True))
            event = _event(metadatas, top_success=True, top_action_return=[])
        else:
            raise AssertionError(f"Unexpected action: {action}")

        self.last_event = event
        return event


class FakeManyPoseController(FakeMultiAgentController):
    def __init__(self):
        super().__init__()
        self._target_object = {
            "objectId": "Bread|many",
            "objectType": "Bread",
            "position": {"x": 0.0, "y": 0.9, "z": 0.0},
            "visible": False,
            "distance": 2.0,
        }
        self._agent_positions = [{"x": -2.0, "y": 0.9, "z": -2.0}, {"x": -2.0, "y": 0.9, "z": -2.0}]
        self.last_event = self._current_event()

    def step(self, action, agentId=None, **kwargs):
        self.actions.append((action, agentId, kwargs))
        far_poses = [
            {"x": -1.0, "y": 0.9, "z": -1.0 - 0.05 * idx, "rotation": 0.0, "horizon": 0.0, "standing": True}
            for idx in range(30)
        ]
        near_pose = {"x": -1.0, "y": 0.9, "z": 0.0, "rotation": 90.0, "horizon": 0.0, "standing": True}

        if action == "GetReachablePositions":
            event = self._query_event(agentId, far_poses + [near_pose])
        elif action == "GetInteractablePoses":
            event = self._query_event(agentId, far_poses + [near_pose])
        elif action == "GetShortestPathToPoint":
            target = dict(kwargs["target"])
            event = self._query_event(agentId, {"corners": [dict(self._agent_positions[agentId]), target]})
        elif action == "TeleportFull":
            self._agent_positions[agentId] = {"x": kwargs["x"], "y": kwargs["y"], "z": kwargs["z"]}
            metadatas = []
            for idx, position in enumerate(self._agent_positions):
                visible = idx == agentId
                distance = 0.55 if visible and round(position["z"], 2) == 0.0 else 1.45
                objects = [dict(self._target_object, visible=visible, distance=distance)]
                metadatas.append(_agent_metadata(position=position, objects=objects, success=True))
            event = _event(metadatas, top_success=True, top_action_return=[])
        else:
            raise AssertionError(f"Unexpected action: {action}")

        self.last_event = event
        return event


class FakeStrictPickupController(FakeMultiAgentController):
    def __init__(self):
        super().__init__()
        self._target_object = {
            "objectId": "Bread|strict",
            "objectType": "Bread",
            "position": {"x": 0.0, "y": 0.9, "z": 0.0},
            "visible": False,
            "distance": 2.0,
        }
        self._agent_positions = [{"x": -2.0, "y": 0.9, "z": -2.0}, {"x": -2.0, "y": 0.9, "z": -2.0}]
        self.last_event = self._current_event()

    def step(self, action, agentId=None, **kwargs):
        self.actions.append((action, agentId, kwargs))
        strict_reject_pose = {"x": -1.0, "y": 0.9, "z": 0.0, "rotation": 90.0, "horizon": 0.0, "standing": True}
        strict_accept_pose = {"x": -1.0, "y": 0.9, "z": -0.25, "rotation": 90.0, "horizon": 0.0, "standing": True}

        if action == "GetReachablePositions":
            event = self._query_event(agentId, [strict_reject_pose, strict_accept_pose])
        elif action == "GetInteractablePoses":
            event = self._query_event(agentId, [strict_reject_pose, strict_accept_pose])
        elif action == "GetShortestPathToPoint":
            target = dict(kwargs["target"])
            event = self._query_event(agentId, {"corners": [dict(self._agent_positions[agentId]), target]})
        elif action == "TeleportFull":
            self._agent_positions[agentId] = {"x": kwargs["x"], "y": kwargs["y"], "z": kwargs["z"]}
            metadatas = []
            for idx, position in enumerate(self._agent_positions):
                visible = idx == agentId
                if visible and round(position["z"], 2) == 0.0:
                    distance = 1.35
                elif visible:
                    distance = 0.65
                else:
                    distance = 3.0
                objects = [dict(self._target_object, visible=visible, distance=distance)]
                metadatas.append(_agent_metadata(position=position, objects=objects, success=True))
            event = _event(metadatas, top_success=True, top_action_return=[])
        else:
            raise AssertionError(f"Unexpected action: {action}")

        self.last_event = event
        return event


class FakeClearanceSensitiveController(FakeMultiAgentController):
    def __init__(self):
        super().__init__()
        self._target_object = {
            "objectId": "Bread|clearance",
            "objectType": "Bread",
            "position": {"x": 0.0, "y": 0.9, "z": 0.0},
            "visible": False,
            "distance": 2.0,
        }
        self._agent_positions = [
            {"x": -1.5, "y": 0.9, "z": 0.0},
            {"x": -2.0, "y": 0.9, "z": -2.0},
        ]
        self.last_event = self._current_event()

    def _query_event(self, agent_id, action_return):
        metadatas = []
        for idx, position in enumerate(self._agent_positions):
            objects = [dict(self._target_object)]
            objects[0]["visible"] = idx == agent_id
            objects[0]["distance"] = 1.0 if idx == agent_id else 3.0
            metadatas.append(
                _agent_metadata(
                    position=position,
                    objects=objects,
                    action_return=action_return if idx == agent_id else [],
                    success=True,
                )
            )
        return _event(metadatas, top_success=True, top_action_return=[])

    def step(self, action, agentId=None, **kwargs):
        self.actions.append((action, agentId, kwargs))
        near_pose = {"x": -1.0, "y": 0.9, "z": 0.0, "rotation": 90.0, "horizon": 0.0, "standing": True}
        far_pose = {"x": -1.0, "y": 0.9, "z": -1.0, "rotation": 45.0, "horizon": 0.0, "standing": True}

        if action == "GetReachablePositions":
            event = self._query_event(agentId, [near_pose, far_pose])
        elif action == "GetInteractablePoses":
            allowed = {
                (round(pos["x"], 2), round(pos["z"], 2))
                for pos in kwargs.get("positions", [])
            }
            returned = [
                pose
                for pose in [near_pose, far_pose]
                if (round(pose["x"], 2), round(pose["z"], 2)) in allowed
            ]
            event = self._query_event(agentId, returned)
        elif action == "GetShortestPathToPoint":
            target = dict(kwargs["target"])
            event = self._query_event(agentId, {"corners": [dict(self._agent_positions[agentId]), target]})
        elif action == "TeleportFull":
            self._agent_positions[agentId] = {"x": kwargs["x"], "y": kwargs["y"], "z": kwargs["z"]}
            metadatas = []
            for idx, position in enumerate(self._agent_positions):
                visible = idx == agentId
                if visible and round(position["z"], 2) == 0.0:
                    distance = 0.6
                elif visible:
                    distance = 1.4
                else:
                    distance = 3.0
                objects = [dict(self._target_object, visible=visible, distance=distance)]
                metadatas.append(_agent_metadata(position=position, objects=objects, success=True))
            event = _event(metadatas, top_success=True, top_action_return=[])
        else:
            raise AssertionError(f"Unexpected action: {action}")

        self.last_event = event
        return event


class FakeUnreliableGeometryController(FakeMultiAgentController):
    def __init__(self):
        super().__init__()
        self._target_object = {
            "objectId": "Plate|weird",
            "objectType": "Plate",
            "position": {"x": 4.0, "y": 0.9, "z": 4.0},
            "visible": False,
            "distance": 4.2,
        }
        self._agent_positions = [{"x": -2.0, "y": 0.9, "z": -2.0}, {"x": -1.0, "y": 0.9, "z": -1.0}]
        self.last_event = self._current_event()

    def step(self, action, agentId=None, **kwargs):
        self.actions.append((action, agentId, kwargs))
        pose = {"x": 0.75, "y": 0.9, "z": 1.5, "rotation": 180.0, "horizon": 0.0, "standing": True}

        if action == "GetReachablePositions":
            event = self._query_event(agentId, [pose])
        elif action == "GetInteractablePoses":
            event = self._query_event(agentId, [pose])
        elif action == "GetShortestPathToPoint":
            target = dict(kwargs["target"])
            event = self._query_event(agentId, {"corners": [dict(self._agent_positions[agentId]), target]})
        elif action == "TeleportFull":
            self._agent_positions[agentId] = {"x": kwargs["x"], "y": kwargs["y"], "z": kwargs["z"]}
            metadatas = []
            for idx, position in enumerate(self._agent_positions):
                visible = idx == agentId
                distance = 4.2 if visible else 3.0
                objects = [dict(self._target_object, visible=visible, distance=distance)]
                metadatas.append(_agent_metadata(position=position, objects=objects, success=True))
            event = _event(metadatas, top_success=True, top_action_return=[])
        else:
            raise AssertionError(f"Unexpected action: {action}")

        self.last_event = event
        return event


class TestNavigationUtils(unittest.TestCase):
    def test_navigate_uses_agent_specific_query_metadata_and_exact_pose_teleport(self):
        controller = FakeMultiAgentController()

        success = navigate_to_object(
            controller,
            agent_id=1,
            object_type="Bread",
            capture_callback=lambda *_args, **_kwargs: None,
            max_distance=1.15,
        )

        self.assertTrue(success)
        self.assertIn("TeleportFull", [action for action, _agent_id, _kwargs in controller.actions])

    def test_navigate_trusts_interactable_pose_even_if_metadata_distance_is_longer(self):
        controller = FakeLongDistanceInteractablePoseController()

        success = navigate_to_object(
            controller,
            agent_id=1,
            object_type="Bread",
            capture_callback=lambda *_args, **_kwargs: None,
            max_distance=1.15,
        )

        self.assertTrue(success)

    def test_navigate_falls_back_to_reachable_pose_when_no_interactable_pose_is_reported(self):
        controller = FakeFallbackPoseController()

        success = navigate_to_object(
            controller,
            agent_id=1,
            object_type="Bread",
            capture_callback=lambda *_args, **_kwargs: None,
            max_distance=1.15,
        )

        self.assertTrue(success)
        self.assertIn("TeleportFull", [action for action, _agent_id, _kwargs in controller.actions])

    def test_navigate_prefers_closer_interactable_pose_over_shorter_path(self):
        controller = FakePoseRankingController()

        success = navigate_to_object(
            controller,
            agent_id=1,
            object_type="Bread",
            capture_callback=lambda *_args, **_kwargs: None,
            max_distance=1.15,
        )

        self.assertTrue(success)
        teleports = [kwargs for action, _agent_id, kwargs in controller.actions if action == "TeleportFull"]
        self.assertTrue(teleports)
        self.assertAlmostEqual(teleports[0]["x"], -1.0)
        self.assertAlmostEqual(teleports[0]["z"], 0.0)

    def test_navigate_considers_close_pose_even_if_it_appears_after_first_24_results(self):
        controller = FakeManyPoseController()

        success = navigate_to_object(
            controller,
            agent_id=1,
            object_type="Bread",
            capture_callback=lambda *_args, **_kwargs: None,
            max_distance=1.15,
        )

        self.assertTrue(success)
        teleports = [kwargs for action, _agent_id, kwargs in controller.actions if action == "TeleportFull"]
        self.assertTrue(teleports)
        self.assertAlmostEqual(teleports[0]["x"], -1.0)
        self.assertAlmostEqual(teleports[0]["z"], 0.0)

    def test_navigate_strict_max_distance_skips_interactable_pose_that_is_still_too_far(self):
        controller = FakeStrictPickupController()

        success = navigate_to_object(
            controller,
            agent_id=1,
            object_type="Bread",
            capture_callback=lambda *_args, **_kwargs: None,
            max_distance=1.15,
            strict_max_distance=True,
        )

        self.assertTrue(success)
        teleports = [kwargs for action, _agent_id, kwargs in controller.actions if action == "TeleportFull"]
        self.assertEqual(len(teleports), 2)
        self.assertAlmostEqual(teleports[0]["z"], 0.0)
        self.assertAlmostEqual(teleports[1]["z"], -0.25)

    def test_navigate_with_tighter_clearance_can_include_pickup_pose_near_other_agent(self):
        controller = FakeClearanceSensitiveController()

        failed = navigate_to_object(
            controller,
            agent_id=1,
            object_type="Bread",
            capture_callback=lambda *_args, **_kwargs: None,
            max_distance=1.15,
            strict_max_distance=True,
        )
        self.assertFalse(failed)

        controller = FakeClearanceSensitiveController()
        success = navigate_to_object(
            controller,
            agent_id=1,
            object_type="Bread",
            capture_callback=lambda *_args, **_kwargs: None,
            max_distance=1.15,
            agent_clearance=TIGHT_INTERACTION_AGENT_CLEARANCE,
            strict_max_distance=True,
        )

        self.assertTrue(success)
        teleports = [kwargs for action, _agent_id, kwargs in controller.actions if action == "TeleportFull"]
        self.assertTrue(teleports)
        self.assertAlmostEqual(teleports[0]["z"], 0.0)

    def test_navigate_relaxes_strict_distance_when_object_geometry_is_unreliable(self):
        controller = FakeUnreliableGeometryController()

        success = navigate_to_object(
            controller,
            agent_id=1,
            object_type="Plate",
            capture_callback=lambda *_args, **_kwargs: None,
            max_distance=1.15,
            strict_max_distance=True,
        )

        self.assertTrue(success)
        teleports = [kwargs for action, _agent_id, kwargs in controller.actions if action == "TeleportFull"]
        self.assertEqual(len(teleports), 1)


if __name__ == "__main__":
    unittest.main()
