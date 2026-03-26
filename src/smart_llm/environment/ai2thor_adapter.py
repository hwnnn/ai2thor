from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from smart_llm.execution.actions import execute_action
from smart_llm.models import EnvironmentObject
from smart_llm.models import ActionResult

try:
    from ai2thor.controller import Controller
except Exception:  # pragma: no cover
    Controller = None  # type: ignore

from .navigation_utils import TIGHT_INTERACTION_AGENT_CLEARANCE, navigate_to_object_iter


THOR_PROFILES = {
    "dev": {
        "scene": "FloorPlan1",
        "width": 800,
        "height": 600,
        "fieldOfView": 90,
        "visibilityDistance": 10.0,
        "snapToGrid": False,
        "targetFrameRate": 10,
    },
    "test": {
        "scene": "FloorPlan1",
        "width": 600,
        "height": 400,
        "fieldOfView": 90,
        "visibilityDistance": 8.0,
        "snapToGrid": False,
        "targetFrameRate": 15,
    },
    "eval": {
        "scene": "FloorPlan1",
        "width": 800,
        "height": 600,
        "fieldOfView": 90,
        "visibilityDistance": 12.0,
        "snapToGrid": False,
        "targetFrameRate": 30,
    },
}

DEFAULT_INTERACTION_DISTANCE = 1.0
PORTABLE_INTERACTION_DISTANCE = 1.15
SWITCH_INTERACTION_DISTANCE = 1.5
FAUCET_INTERACTION_DISTANCE = 1.35
RECEPTACLE_INTERACTION_DISTANCE = 1.35


@dataclass
class ThorContext:
    controller: Optional[Any]
    agent_count: int


class AI2ThorAdapter:
    def __init__(
        self,
        profile: str = "dev",
        dry_run: bool = False,
        record_overhead_video: bool = False,
        record_agent_video: bool = False,
        output_dir: str = "output_videos",
        observer_fov: float = 35.0,
        observer_height_padding: float = 0.0,
    ):
        if profile not in THOR_PROFILES:
            raise ValueError(f"Unknown profile: {profile}")
        self.profile = profile
        self.dry_run = dry_run
        self.record_overhead_video = record_overhead_video and not dry_run
        self.record_agent_video = record_agent_video and not dry_run
        self.output_dir = Path(output_dir)
        self.observer_fov = observer_fov
        self.observer_height_padding = observer_height_padding
        self.frame_rate = THOR_PROFILES[self.profile]["targetFrameRate"]
        self.context = ThorContext(controller=None, agent_count=0)
        self.mock_objects: List[Dict[str, Any]] = []
        self.observer_camera_id: Optional[int] = None
        self.observer_video_path: Optional[str] = None
        self.agent_video_paths: Dict[str, str] = {}
        self._recording_timestamp: Optional[str] = None
        self._observer_writer = None
        self._agent_writers: Dict[int, Any] = {}
        self.max_interaction_distance = DEFAULT_INTERACTION_DISTANCE
        self.max_receptacle_distance = RECEPTACLE_INTERACTION_DISTANCE

    def _interaction_distance_for(self, object_type: str | None, *, portable: bool = False) -> float | None:
        if object_type == "LightSwitch":
            return SWITCH_INTERACTION_DISTANCE
        if object_type == "Faucet":
            return FAUCET_INTERACTION_DISTANCE
        if object_type in {"Fridge", "Microwave", "SinkBasin", "Cabinet", "Drawer", "CounterTop"}:
            return None
        if portable:
            return PORTABLE_INTERACTION_DISTANCE
        return self.max_interaction_distance

    def _coalesce(self, *values):
        for value in values:
            if value is not None:
                return value
        return None

    def _tight_interaction_navigation_kwargs(self, max_distance: float | None) -> Dict[str, Any]:
        return {
            "max_distance": max_distance,
            "agent_clearance": TIGHT_INTERACTION_AGENT_CLEARANCE,
            "strict_max_distance": True,
        }

    def start(self, agent_count: int) -> None:
        self.context.agent_count = agent_count
        if self.dry_run:
            self._reset_mock_world()
            return

        if Controller is None:
            raise RuntimeError(
                "ai2thor is not installed. Run `pip install -r requirements.txt` "
                "or `pip install ai2thor==5.0.0` in your active environment."
            )

        config = dict(THOR_PROFILES[self.profile])
        self.context.controller = Controller(agentCount=agent_count, **config)
        if self.record_overhead_video:
            self._setup_overhead_camera()
        if self.record_agent_video:
            self.capture_agent_frames(self.context.controller.last_event)

    def stop(self) -> None:
        if self._observer_writer is not None:
            self._observer_writer.release()
            self._observer_writer = None
        for writer in self._agent_writers.values():
            writer.release()
        self._agent_writers = {}
        if self.context.controller is not None:
            self.context.controller.stop()
            self.context.controller = None

    def _metadata(self, agent_id: int = 0) -> Dict[str, Any]:
        if self.context.controller is None:
            return {"objects": []}
        if self.context.agent_count > 1:
            return self.context.controller.last_event.events[agent_id].metadata
        return self.context.controller.last_event.metadata

    def _event_metadata(self, event: Any, agent_id: int = 0) -> Dict[str, Any]:
        if self.context.agent_count > 1:
            events = getattr(event, "events", None) or []
            if 0 <= agent_id < len(events):
                return events[agent_id].metadata
        return getattr(event, "metadata", {}) or {}

    def _last_action_success(self, event: Any, agent_id: int = 0) -> bool:
        return bool(self._event_metadata(event, agent_id).get("lastActionSuccess"))

    def _action_return(self, event: Any, agent_id: int = 0) -> Any:
        return self._event_metadata(event, agent_id).get("actionReturn")

    def _reset_mock_world(self) -> None:
        self.mock_objects = [
            {
                "objectId": "Tomato|1",
                "objectType": "Tomato",
                "visible": True,
                "position": {"x": 0.1, "y": 0.9, "z": -1.1},
                "isSliced": False,
            },
            {
                "objectId": "Fridge|1",
                "objectType": "Fridge",
                "visible": True,
                "position": {"x": -0.2, "y": 0.0, "z": 1.4},
                "isOpen": False,
                "receptacleObjectIds": [],
            },
            {
                "objectId": "LightSwitch|1",
                "objectType": "LightSwitch",
                "visible": True,
                "position": {"x": 1.0, "y": 1.1, "z": -0.3},
                "isToggled": True,
            },
            {
                "objectId": "Bread|1",
                "objectType": "Bread",
                "visible": True,
                "position": {"x": 0.5, "y": 0.9, "z": 0.3},
            },
            {
                "objectId": "Microwave|1",
                "objectType": "Microwave",
                "visible": True,
                "position": {"x": -0.8, "y": 1.0, "z": 0.9},
                "isOpen": False,
                "isToggled": False,
                "receptacleObjectIds": [],
            },
            {
                "objectId": "Plate|1",
                "objectType": "Plate",
                "visible": True,
                "position": {"x": 0.6, "y": 0.9, "z": -0.5},
            },
            {
                "objectId": "SinkBasin|1",
                "objectType": "SinkBasin",
                "visible": True,
                "position": {"x": 1.1, "y": 0.9, "z": 1.0},
                "receptacleObjectIds": [],
            },
            {
                "objectId": "Faucet|1",
                "objectType": "Faucet",
                "visible": True,
                "position": {"x": 1.1, "y": 1.2, "z": 1.0},
                "isToggled": False,
            },
        ]

    def _setup_overhead_camera(self) -> None:
        if self.context.controller is None:
            return

        map_view = self.context.controller.step(action="GetMapViewCameraProperties")
        props = self._action_return(map_view) or {}
        if props:
            props = dict(props)
            if "orthographicSize" in props:
                props["orthographicSize"] = float(props["orthographicSize"]) + float(self.observer_height_padding)
            event = self.context.controller.step(action="AddThirdPartyCamera", **props)
        else:
            bounds = self.context.controller.last_event.metadata["sceneBounds"]
            center = bounds["center"]
            size = bounds["size"]
            half_extent = max(float(size["x"]), float(size["z"])) / 2.0
            fov_radians = math.radians(max(self.observer_fov, 5.0) / 2.0)
            height_above_center = half_extent / max(math.tan(fov_radians), 1e-3)
            camera_y = center["y"] + height_above_center + self.observer_height_padding
            event = self.context.controller.step(
                action="AddThirdPartyCamera",
                position=dict(x=center["x"], y=camera_y, z=center["z"]),
                rotation=dict(x=90, y=0, z=0),
                fieldOfView=self.observer_fov,
            )
        frames = getattr(event, "third_party_camera_frames", None) or []
        if not frames and getattr(event, "events", None):
            frames = getattr(event.events[0], "third_party_camera_frames", None) or []
        self.observer_camera_id = len(frames) - 1 if frames else 0
        self.capture_recordings(event)

    def _recording_stamp(self) -> str:
        if self._recording_timestamp is None:
            self._recording_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self._recording_timestamp

    def _write_video_frame(self, frame, writer_attr: str, path_attr: str, prefix: str, frame_id: int | None = None) -> None:
        import cv2

        self.output_dir.mkdir(parents=True, exist_ok=True)
        writer = getattr(self, writer_attr, None)
        if writer is None:
            suffix = f"_{frame_id}" if frame_id is not None else ""
            path = str(self.output_dir / f"{prefix}{suffix}_{self._recording_stamp()}.mp4")
            height, width = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(path, fourcc, self.frame_rate, (width, height))
            setattr(self, writer_attr, writer)
            setattr(self, path_attr, path)
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

    def capture_overhead_frame(self, event=None) -> None:
        if not self.record_overhead_video or self.context.controller is None or self.observer_camera_id is None:
            return

        event = self._coalesce(event, self.context.controller.last_event)
        frames = self._coalesce(getattr(event, "third_party_camera_frames", None), [])
        if not frames:
            frames = self._coalesce(getattr(self.context.controller.last_event, "third_party_camera_frames", None), [])
        if not frames and getattr(event, "events", None):
            frames = self._coalesce(getattr(event.events[0], "third_party_camera_frames", None), [])
        if not frames and getattr(self.context.controller.last_event, "events", None):
            frames = self._coalesce(
                getattr(self.context.controller.last_event.events[0], "third_party_camera_frames", None),
                [],
            )
        if self.observer_camera_id >= len(frames):
            return

        frame = frames[self.observer_camera_id]
        self._write_video_frame(frame, "_observer_writer", "observer_video_path", "overhead")

    def capture_agent_frames(self, event=None) -> None:
        if not self.record_agent_video or self.context.controller is None:
            return

        event = self._coalesce(event, self.context.controller.last_event)
        if self.context.agent_count > 1:
            agent_events = self._coalesce(
                getattr(event, "events", None),
                getattr(self.context.controller.last_event, "events", None),
                [],
            )
            frames = [(idx, agent_event.frame) for idx, agent_event in enumerate(agent_events) if getattr(agent_event, "frame", None) is not None]
        else:
            frame = self._coalesce(
                getattr(event, "frame", None),
                getattr(self.context.controller.last_event, "frame", None),
            )
            frames = [(0, frame)] if frame is not None else []

        for agent_id, frame in frames:
            if frame is None:
                continue
            if agent_id not in self._agent_writers:
                import cv2

                self.output_dir.mkdir(parents=True, exist_ok=True)
                path = str(self.output_dir / f"agent{agent_id}_{self._recording_stamp()}.mp4")
                height, width = frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                self._agent_writers[agent_id] = cv2.VideoWriter(path, fourcc, self.frame_rate, (width, height))
                self.agent_video_paths[f"agent{agent_id}"] = path

            import cv2

            self._agent_writers[agent_id].write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

    def capture_recordings(self, event=None) -> None:
        self.capture_overhead_frame(event)
        self.capture_agent_frames(event)

    def artifacts(self) -> Dict[str, Any]:
        artifacts = {}
        if self.observer_video_path:
            artifacts["overhead_video"] = self.observer_video_path
        if self.agent_video_paths:
            artifacts["agent_videos"] = dict(self.agent_video_paths)
        return artifacts

    def _object_rows(self, agent_id: int = 0) -> List[Dict[str, Any]]:
        if self.dry_run:
            return self.mock_objects
        return list(self._metadata(agent_id).get("objects", []))

    def _inventory_rows(self, agent_id: int = 0) -> List[Dict[str, Any]]:
        if self.dry_run:
            return []
        return list(self._metadata(agent_id).get("inventoryObjects", []))

    def _inventory_contains(self, object_types: List[str], agent_id: int = 0) -> bool:
        inventory_types = {obj.get("objectType") for obj in self._inventory_rows(agent_id)}
        return any(object_type in inventory_types for object_type in object_types)

    def list_environment_objects(self, agent_id: int = 0) -> List[EnvironmentObject]:
        objects = []
        for obj in self._object_rows(agent_id):
            objects.append(
                EnvironmentObject(
                    objectType=obj.get("objectType", "Unknown"),
                    state={
                        "visible": obj.get("visible"),
                        "isOpen": obj.get("isOpen"),
                        "isToggled": obj.get("isToggled"),
                        "isPickedUp": obj.get("isPickedUp"),
                    },
                    position=obj.get("position", {}),
                    affordance=obj.get("salientMaterials", []),
                )
            )
        return objects

    def _find_visible(
        self,
        object_type: str,
        agent_id: int = 0,
        max_distance: float | None = None,
    ) -> Optional[Dict[str, Any]]:
        matches = []
        for obj in self._object_rows(agent_id):
            if obj.get("objectType") != object_type or not obj.get("visible"):
                continue
            if max_distance is not None:
                distance = obj.get("distance")
                if distance is not None and float(distance) > max_distance:
                    continue
            matches.append(obj)
        if not matches:
            return None
        return min(matches, key=lambda row: float(row.get("distance", 999.0)))

    def _find_any(self, object_type: str, agent_id: int = 0) -> Optional[Dict[str, Any]]:
        for obj in self._object_rows(agent_id):
            if obj.get("objectType") == object_type:
                return obj
        return None

    def _find_by_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        for obj in self.mock_objects:
            if obj.get("objectId") == object_id:
                return obj
        return None

    def check_precondition(
        self,
        task_type: str,
        parameters: Dict[str, Any],
        agent_id: int = 0,
        step_name: str | None = None,
    ) -> bool:
        _ = step_name

        if task_type == "slice_and_store":
            source = parameters.get("source_object")
            target = parameters.get("target_object")
            return bool(source and target and self._find_any(target, agent_id) and (self._find_any(source, agent_id) or self._find_any(source + "Sliced", agent_id)))
        if task_type == "toggle_light":
            return parameters.get("action") in {"켜기", "끄기"} and self._find_any("LightSwitch", agent_id) is not None
        if task_type == "heat_object":
            obj_type = parameters.get("object")
            return self._find_any(obj_type, agent_id) is not None and self._find_any("Microwave", agent_id) is not None
        if task_type == "clean_object":
            obj_type = parameters.get("object")
            return (
                obj_type is not None
                and self._find_any(obj_type, agent_id) is not None
                and self._find_any("SinkBasin", agent_id) is not None
                and self._find_any("Faucet", agent_id) is not None
            )
        if task_type == "navigate":
            target_object = parameters.get("target_object")
            return bool(target_object) and self._find_any(target_object, agent_id) is not None
        return False

    def _remove_from_receptacles(self, object_id: str) -> None:
        for obj in self.mock_objects:
            receptacle_ids = obj.get("receptacleObjectIds")
            if isinstance(receptacle_ids, list) and object_id in receptacle_ids:
                receptacle_ids.remove(object_id)

    def _ensure_mock_sliced(self, source_object: str) -> Optional[Dict[str, Any]]:
        sliced_type = source_object + "Sliced"
        sliced = self._find_by_id(f"{sliced_type}|1")
        if sliced is not None:
            sliced["visible"] = True
            return sliced

        source = self._find_by_id(f"{source_object}|1")
        if source is None:
            return None

        source["visible"] = False
        source["isSliced"] = True
        sliced = {
            "objectId": f"{sliced_type}|1",
            "objectType": sliced_type,
            "visible": True,
            "position": dict(source.get("position", {})),
        }
        self.mock_objects.append(sliced)
        return sliced

    def _mock_store_in(self, object_type: str, target_type: str) -> bool:
        obj = self._find_any(object_type)
        container = self._find_any(target_type)
        if obj is None or container is None:
            return False
        self._remove_from_receptacles(obj["objectId"])
        container.setdefault("receptacleObjectIds", []).append(obj["objectId"])
        obj["visible"] = False
        obj["parentReceptacles"] = [container["objectId"]]
        return True

    def _execute_mock_step(self, task_type: str, step_name: str, parameters: Dict[str, Any], agent_id: int = 0) -> bool:
        _ = agent_id
        if task_type == "navigate" and step_name == "navigate":
            target_object = parameters.get("target_object")
            return bool(target_object) and self._find_any(target_object) is not None

        if task_type == "toggle_light" and step_name == "navigate_and_toggle":
            switch = self._find_any("LightSwitch")
            if switch is None:
                return False
            switch["isToggled"] = parameters.get("action", "끄기") == "켜기"
            return True

        if task_type == "slice_and_store":
            source_object = parameters.get("source_object", "Tomato")
            target_object = parameters.get("target_object", "Fridge")
            if step_name == "prepare_source":
                return self._ensure_mock_sliced(source_object) is not None
            if step_name == "transport_and_store":
                sliced = self._ensure_mock_sliced(source_object)
                if sliced is None:
                    return False
                return self._mock_store_in(sliced["objectType"], target_object)

        if task_type == "heat_object":
            obj_type = parameters.get("object", "Bread")
            microwave = self._find_any("Microwave")
            if microwave is None:
                return False
            if step_name == "load_microwave":
                microwave["isOpen"] = True
                stored = self._mock_store_in(obj_type, "Microwave")
                microwave["isOpen"] = False
                return stored
            if step_name == "activate_microwave":
                microwave["isOpen"] = False
                microwave["isToggled"] = True
                return True

        if task_type == "clean_object":
            obj_type = parameters.get("object", "Plate")
            if step_name == "place_in_sink":
                return self._mock_store_in(obj_type, "SinkBasin")
            if step_name == "toggle_faucet":
                faucet = self._find_any("Faucet")
                if faucet is None:
                    return False
                faucet["isToggled"] = True
                return True

        return False

    def _ensure_open(self, target: Dict[str, Any], agent_id: int) -> bool:
        if target.get("isOpen"):
            return True
        event = self.context.controller.step(action="OpenObject", objectId=target["objectId"], agentId=agent_id)
        self.capture_recordings(event)
        return self._last_action_success(event, agent_id)

    def _ensure_closed(self, target: Dict[str, Any], agent_id: int) -> bool:
        if not target.get("isOpen"):
            return True
        event = self.context.controller.step(action="CloseObject", objectId=target["objectId"], agentId=agent_id)
        self.capture_recordings(event)
        return self._last_action_success(event, agent_id)

    def _pick_visible(self, object_type: str, agent_id: int, max_distance: float | None = None) -> bool:
        obj = self._find_visible(object_type, agent_id, max_distance=max_distance)
        if obj is None:
            return False
        event = self.context.controller.step(action="PickupObject", objectId=obj["objectId"], agentId=agent_id)
        self.capture_recordings(event)
        return self._last_action_success(event, agent_id)

    def _toggle_visible(
        self,
        object_type: str,
        thor_action: str,
        agent_id: int,
        max_distance: float | None = None,
    ) -> bool:
        obj = self._find_visible(object_type, agent_id, max_distance=max_distance)
        if obj is None:
            return False
        event = self.context.controller.step(action=thor_action, objectId=obj["objectId"], agentId=agent_id)
        self.capture_recordings(event)
        return self._last_action_success(event, agent_id)

    def _action_result(self, ok: bool, message: str, transitions: int = 1) -> ActionResult:
        status = "success" if ok else "failure"
        return ActionResult(success=ok, status=status, message=message, transitions=transitions)

    def _emit_execute_action(self, action_fn, action_name: str) -> Generator[ActionResult, None, bool]:
        result = execute_action(action_fn, action_name)
        yield result
        return result.success

    def execute_step_iter(
        self,
        task_type: str,
        step_name: str,
        parameters: Dict[str, Any],
        agent_id: int = 0,
    ) -> Generator[ActionResult, None, bool]:
        if self.dry_run:
            ok = self._execute_mock_step(task_type, step_name, parameters, agent_id=agent_id)
            yield self._action_result(ok, f"{task_type}:{step_name}:mock", transitions=1)
            return ok

        if self.context.controller is None:
            raise RuntimeError("AI2-THOR controller is not started")

        capture_callback = self.capture_recordings

        if task_type == "navigate" and step_name == "navigate":
            target = parameters.get("target_object")
            if not target:
                yield self._action_result(False, f"{task_type}:{step_name}:missing_target", transitions=0)
                return False
            return (
                yield from navigate_to_object_iter(
                    self.context.controller,
                    agent_id,
                    target,
                    capture_callback,
                    max_distance=self._interaction_distance_for(target),
                )
            )

        if task_type == "toggle_light" and step_name == "navigate_and_toggle":
            action = parameters.get("action")
            if action not in {"켜기", "끄기"}:
                yield self._action_result(False, f"{task_type}:{step_name}:missing_action", transitions=0)
                return False
            max_distance = self._interaction_distance_for("LightSwitch")
            navigated = yield from navigate_to_object_iter(
                self.context.controller,
                agent_id,
                "LightSwitch",
                capture_callback,
                max_distance=max_distance,
            )
            if not navigated:
                return False
            thor_action = "ToggleObjectOn" if action == "켜기" else "ToggleObjectOff"
            return (yield from self._emit_execute_action(
                lambda: self._toggle_visible(
                        "LightSwitch",
                        thor_action,
                        agent_id,
                    ),
                    f"{task_type}:{step_name}:toggle",
                ))

        if task_type == "slice_and_store":
            source_object = parameters.get("source_object")
            target_object = parameters.get("target_object")
            if not source_object or not target_object:
                yield self._action_result(False, f"{task_type}:{step_name}:missing_parameters", transitions=0)
                return False

            if step_name == "prepare_source":
                source_distance = self._interaction_distance_for(source_object, portable=True)
                if self._find_any(source_object + "Sliced", agent_id):
                    yield self._action_result(True, f"{task_type}:{step_name}:already_sliced", transitions=0)
                    return True
                navigated = yield from navigate_to_object_iter(
                    self.context.controller,
                    agent_id,
                    source_object,
                    capture_callback,
                    **self._tight_interaction_navigation_kwargs(source_distance),
                )
                if not navigated:
                    return False
                source = self._find_visible(source_object, agent_id)
                if source is None:
                    yield self._action_result(False, f"{task_type}:{step_name}:source_not_visible", transitions=0)
                    return False
                event = self.context.controller.step(action="SliceObject", objectId=source["objectId"], agentId=agent_id)
                self.capture_recordings(event)
                ok = self._last_action_success(event, agent_id)
                yield self._action_result(ok, f"{task_type}:{step_name}:slice")
                return ok

            if step_name == "transport_and_store":
                carrying_source = self._inventory_contains([source_object + "Sliced", source_object], agent_id=agent_id)
                pickup_distance = self._interaction_distance_for(source_object, portable=True)
                target_distance = self._interaction_distance_for(target_object)
                if not carrying_source:
                    pickup_target = source_object + "Sliced" if self._find_any(source_object + "Sliced", agent_id) else source_object
                    navigated = yield from navigate_to_object_iter(
                        self.context.controller,
                        agent_id,
                        pickup_target,
                        capture_callback,
                        **self._tight_interaction_navigation_kwargs(pickup_distance),
                    )
                    if not navigated:
                        return False
                    sliced = self._find_visible(source_object + "Sliced", agent_id)
                    if sliced is None:
                        yield self._action_result(False, f"{task_type}:{step_name}:sliced_not_visible", transitions=0)
                        return False
                    picked = yield from self._emit_execute_action(
                        lambda: self._pick_visible(
                            sliced["objectType"],
                            agent_id,
                        ),
                        f"{task_type}:{step_name}:pickup",
                    )
                    if not picked:
                        return False
                navigated = yield from navigate_to_object_iter(
                    self.context.controller,
                    agent_id,
                    target_object,
                    capture_callback,
                    max_distance=target_distance,
                )
                if not navigated:
                    return False
                target = self._find_visible(target_object, agent_id)
                if target is None:
                    yield self._action_result(False, f"{task_type}:{step_name}:target_not_visible", transitions=0)
                    return False
                opened = yield from self._emit_execute_action(
                    lambda: self._ensure_open(target, agent_id),
                    f"{task_type}:{step_name}:open",
                )
                if not opened:
                    return False
                put_event = self.context.controller.step(
                    action="PutObject",
                    objectId=target["objectId"],
                    forceAction=True,
                    agentId=agent_id,
                )
                self.capture_recordings(put_event)
                ok = self._last_action_success(put_event, agent_id)
                yield self._action_result(ok, f"{task_type}:{step_name}:put")
                return ok

        if task_type == "heat_object":
            obj_type = parameters.get("object")
            portable_distance = self._interaction_distance_for(obj_type, portable=True)
            microwave_distance = self._interaction_distance_for("Microwave")
            if step_name == "load_microwave":
                if not obj_type:
                    yield self._action_result(False, f"{task_type}:{step_name}:missing_object", transitions=0)
                    return False
                navigated = yield from navigate_to_object_iter(
                    self.context.controller,
                    agent_id,
                    obj_type,
                    capture_callback,
                    **self._tight_interaction_navigation_kwargs(portable_distance),
                )
                if not navigated:
                    return False
                picked = yield from self._emit_execute_action(
                    lambda: self._pick_visible(
                        obj_type,
                        agent_id,
                    ),
                    f"{task_type}:{step_name}:pickup",
                )
                if not picked:
                    return False
                navigated = yield from navigate_to_object_iter(
                    self.context.controller,
                    agent_id,
                    "Microwave",
                    capture_callback,
                    max_distance=microwave_distance,
                )
                if not navigated:
                    return False
                microwave = self._find_visible("Microwave", agent_id)
                if microwave is None:
                    yield self._action_result(False, f"{task_type}:{step_name}:microwave_not_visible", transitions=0)
                    return False
                opened = yield from self._emit_execute_action(
                    lambda: self._ensure_open(microwave, agent_id),
                    f"{task_type}:{step_name}:open",
                )
                if not opened:
                    return False
                put_event = self.context.controller.step(
                    action="PutObject",
                    objectId=microwave["objectId"],
                    forceAction=True,
                    agentId=agent_id,
                )
                self.capture_recordings(put_event)
                put_ok = self._last_action_success(put_event, agent_id)
                yield self._action_result(put_ok, f"{task_type}:{step_name}:put")
                if not put_ok:
                    return False
                microwave = self._find_visible("Microwave", agent_id)
                if microwave is None:
                    yield self._action_result(False, f"{task_type}:{step_name}:microwave_lost", transitions=0)
                    return False
                return (yield from self._emit_execute_action(
                    lambda: self._ensure_closed(microwave, agent_id),
                    f"{task_type}:{step_name}:close",
                ))
            if step_name == "activate_microwave":
                navigated = yield from navigate_to_object_iter(
                    self.context.controller,
                    agent_id,
                    "Microwave",
                    capture_callback,
                    max_distance=microwave_distance,
                )
                if not navigated:
                    return False
                microwave = self._find_visible("Microwave", agent_id)
                if microwave is None:
                    yield self._action_result(False, f"{task_type}:{step_name}:microwave_not_visible", transitions=0)
                    return False
                closed = yield from self._emit_execute_action(
                    lambda: self._ensure_closed(microwave, agent_id),
                    f"{task_type}:{step_name}:close",
                )
                if not closed:
                    return False
                return (yield from self._emit_execute_action(
                    lambda: self._toggle_visible(
                        "Microwave",
                        "ToggleObjectOn",
                        agent_id,
                    ),
                    f"{task_type}:{step_name}:toggle",
                ))

        if task_type == "clean_object":
            obj_type = parameters.get("object")
            portable_distance = self._interaction_distance_for(obj_type, portable=True)
            sink_distance = self._interaction_distance_for("SinkBasin")
            faucet_distance = self._interaction_distance_for("Faucet")
            if step_name == "place_in_sink":
                if not obj_type:
                    yield self._action_result(False, f"{task_type}:{step_name}:missing_object", transitions=0)
                    return False
                navigated = yield from navigate_to_object_iter(
                    self.context.controller,
                    agent_id,
                    obj_type,
                    capture_callback,
                    **self._tight_interaction_navigation_kwargs(portable_distance),
                )
                if not navigated:
                    return False
                picked = yield from self._emit_execute_action(
                    lambda: self._pick_visible(
                        obj_type,
                        agent_id,
                    ),
                    f"{task_type}:{step_name}:pickup",
                )
                if not picked:
                    return False
                navigated = yield from navigate_to_object_iter(
                    self.context.controller,
                    agent_id,
                    "SinkBasin",
                    capture_callback,
                    max_distance=sink_distance,
                )
                if not navigated:
                    return False
                sink = self._find_visible("SinkBasin", agent_id)
                if sink is None:
                    yield self._action_result(False, f"{task_type}:{step_name}:sink_not_visible", transitions=0)
                    return False
                put_event = self.context.controller.step(
                    action="PutObject",
                    objectId=sink["objectId"],
                    forceAction=True,
                    agentId=agent_id,
                )
                self.capture_recordings(put_event)
                ok = self._last_action_success(put_event, agent_id)
                yield self._action_result(ok, f"{task_type}:{step_name}:put")
                return ok
            if step_name == "toggle_faucet":
                navigated = yield from navigate_to_object_iter(
                    self.context.controller,
                    agent_id,
                    "Faucet",
                    capture_callback,
                    max_distance=faucet_distance,
                )
                if not navigated:
                    return False
                return (yield from self._emit_execute_action(
                    lambda: self._toggle_visible(
                        "Faucet",
                        "ToggleObjectOn",
                        agent_id,
                    ),
                    f"{task_type}:{step_name}:toggle",
                ))

        yield self._action_result(False, f"{task_type}:{step_name}:unsupported", transitions=0)
        return False

    def execute_step(self, task_type: str, step_name: str, parameters: Dict[str, Any], agent_id: int = 0) -> bool:
        success = True
        for result in self.execute_step_iter(task_type, step_name, parameters, agent_id=agent_id):
            success = result.success
            if not result.success:
                return False
        return success

    def execute_task(self, task_type: str, parameters: Dict[str, Any], agent_id: int = 0) -> bool:
        step_sequences = {
            "navigate": ["navigate"],
            "toggle_light": ["navigate_and_toggle"],
            "slice_and_store": ["prepare_source", "transport_and_store"],
            "heat_object": ["load_microwave", "activate_microwave"],
            "clean_object": ["place_in_sink", "toggle_faucet"],
        }

        steps = step_sequences.get(task_type)
        if steps is None:
            return False

        for step_name in steps:
            if not self.execute_step(task_type, step_name, parameters, agent_id=agent_id):
                return False
        return True

    def evaluate_goal_states(self, goal_states: List[Dict[str, Any]] | None, agent_id: int = 0) -> List[bool]:
        if not goal_states:
            return []

        objects = self._object_rows(agent_id)
        object_types_by_id = {obj.get("objectId"): obj.get("objectType") for obj in objects if obj.get("objectId")}
        results: List[bool] = []

        for goal in goal_states:
            object_type = goal.get("objectType")
            expected_state = goal.get("state", {})
            matches = [obj for obj in objects if obj.get("objectType") == object_type]

            exists_expected = expected_state.get("exists")
            if exists_expected is not None:
                results.append(bool(matches) is bool(exists_expected))
                continue

            satisfied = False
            for obj in matches:
                state_ok = True
                for key, expected in expected_state.items():
                    if key == "contains":
                        contained_types = [
                            object_types_by_id.get(object_id)
                            for object_id in obj.get("receptacleObjectIds", [])
                        ]
                        if expected not in contained_types:
                            state_ok = False
                            break
                    elif obj.get(key) != expected:
                        state_ok = False
                        break
                if state_ok:
                    satisfied = True
                    break

            results.append(satisfied)

        return results
