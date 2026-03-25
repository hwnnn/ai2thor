from __future__ import annotations

import unittest
import sys
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
