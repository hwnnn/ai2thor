from __future__ import annotations

ROBOT_SKILL_SCHEMA = {
    "type": "object",
    "required": ["robot_id", "skills"],
    "properties": {
        "robot_id": {"type": "string", "minLength": 1},
        "skills": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
        },
        "constraints": {
            "type": "array",
            "items": {"type": "string"},
        },
        "capabilities": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}

ENVIRONMENT_OBJECT_SCHEMA = {
    "type": "object",
    "required": ["objectType", "state", "position", "affordance"],
    "properties": {
        "objectType": {"type": "string", "minLength": 1},
        "state": {"type": "object"},
        "position": {
            "type": "object",
            "required": ["x", "y", "z"],
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
                "z": {"type": "number"},
            },
        },
        "affordance": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}

STAGE1_SCHEMA = {
    "type": "object",
    "required": ["subtasks"],
    "properties": {
        "subtasks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "subtask_id",
                    "task_type",
                    "description",
                    "required_skills",
                    "dependencies",
                    "parallelizable",
                    "parameters",
                    "code_draft",
                ],
                "properties": {
                    "subtask_id": {"type": "string", "minLength": 1},
                    "task_type": {"type": "string", "minLength": 1},
                    "description": {"type": "string", "minLength": 1},
                    "required_skills": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "parallelizable": {"type": "boolean"},
                    "parameters": {"type": "object"},
                    "code_draft": {"type": "string"},
                },
            },
        }
    },
}

STAGE2_SCHEMA = {
    "type": "object",
    "required": ["coalitions", "coalition_policy_text"],
    "properties": {
        "coalitions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "subtask_id",
                    "required_skills",
                    "single_robot_possible",
                    "min_team_size",
                    "candidate_teams",
                ],
                "properties": {
                    "subtask_id": {"type": "string"},
                    "required_skills": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "single_robot_possible": {"type": "boolean"},
                    "min_team_size": {"type": "integer", "minimum": 1},
                    "candidate_teams": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                    },
                },
            },
        },
        "coalition_policy_text": {"type": "string"},
    },
}

STAGE3_SCHEMA = {
    "type": "object",
    "required": ["allocations", "barriers", "executable_plan"],
    "properties": {
        "allocations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["subtask_id", "assigned_robots", "thread_group", "dependencies"],
                "properties": {
                    "subtask_id": {"type": "string"},
                    "assigned_robots": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                    "thread_group": {"type": "integer", "minimum": 0},
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "barriers": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "executable_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "subtask_id",
                    "task_type",
                    "parameters",
                    "assigned_robots",
                    "thread_group",
                    "dependencies",
                ],
                "properties": {
                    "subtask_id": {"type": "string"},
                    "task_type": {"type": "string"},
                    "parameters": {"type": "object"},
                    "assigned_robots": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                    "thread_group": {"type": "integer", "minimum": 0},
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    },
}
