from __future__ import annotations

from types import SimpleNamespace
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smart_llm.environment import AI2ThorAdapter


class TestEnvironmentAdapter(unittest.TestCase):
    def test_heat_object_closes_microwave_before_activation(self):
        env = AI2ThorAdapter(profile="dev", dry_run=True)
        env.start(agent_count=1)
        self.assertTrue(env.execute_step("heat_object", "load_microwave", {"object": "Bread"}, agent_id=0))
        self.assertTrue(env.execute_step("heat_object", "activate_microwave", {"object": "Bread"}, agent_id=0))

        microwave_state = env.evaluate_goal_states(
            [{"objectType": "Microwave", "state": {"isOpen": False, "isToggled": True}}]
        )
        self.assertEqual(microwave_state, [True])

    def test_find_visible_respects_max_distance(self):
        env = AI2ThorAdapter(profile="dev", dry_run=True)
        env.start(agent_count=1)
        tomato = next(obj for obj in env.mock_objects if obj["objectType"] == "Tomato")
        tomato["distance"] = 2.0

        self.assertIsNone(env._find_visible("Tomato", agent_id=0, max_distance=1.0))
        self.assertIsNotNone(env._find_visible("Tomato", agent_id=0, max_distance=2.5))

    def test_navigate_requires_explicit_target_object(self):
        env = AI2ThorAdapter(profile="dev", dry_run=True)
        env.start(agent_count=1)

        self.assertFalse(env.check_precondition("navigate", {}, agent_id=0))
        self.assertFalse(env.execute_step("navigate", "navigate", {}, agent_id=0))

    def test_object_specific_interaction_distances(self):
        env = AI2ThorAdapter(profile="dev", dry_run=True)

        self.assertGreater(env._interaction_distance_for("LightSwitch"), env._interaction_distance_for("Tomato", portable=True))
        self.assertGreaterEqual(env._interaction_distance_for("Faucet"), env._interaction_distance_for("Tomato", portable=True))
        self.assertIsNone(env._interaction_distance_for("Fridge"))

    def test_capture_agent_frames_handles_numpy_frame_without_truthiness_error(self):
        class DummyWriter:
            def __init__(self):
                self.frames = 0

            def write(self, frame):
                _ = frame
                self.frames += 1

        class FragileFrame:
            shape = (4, 4, 3)

            def __bool__(self):
                raise ValueError("truth-value should not be evaluated")

        env = AI2ThorAdapter(profile="dev", dry_run=False, record_agent_video=True)
        env.context.controller = SimpleNamespace(last_event=None)
        env.context.agent_count = 1

        frame = FragileFrame()
        event = SimpleNamespace(frame=frame)
        env.context.controller.last_event = event
        env._agent_writers[0] = DummyWriter()

        fake_cv2 = SimpleNamespace(
            cvtColor=lambda value, _: value,
            COLOR_RGB2BGR=0,
        )
        with patch.dict(sys.modules, {"cv2": fake_cv2}):
            env.capture_agent_frames(event)

        self.assertEqual(env._agent_writers[0].frames, 1)


if __name__ == "__main__":
    unittest.main()
