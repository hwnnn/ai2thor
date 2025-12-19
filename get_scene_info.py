#!/usr/bin/env python3
"""
AI2THOR Scene 정보 조회 유틸리티
- Scene의 경계, 크기
- 모든 객체의 위치와 타입
- 이동 가능한 영역
"""

from ai2thor.controller import Controller
import json


def get_detailed_scene_info(scene_name="FloorPlan1"):
    """Scene의 상세 정보 조회"""
    
    print(f"{'=' * 60}")
    print(f"Scene: {scene_name} 정보 조회")
    print(f"{'=' * 60}\n")
    
    # Controller 초기화
    print("Controller 초기화 중...")
    controller = Controller(
        agentMode="default",
        scene=scene_name,
        gridSize=0.25,
        width=800,
        height=600
    )
    print("✓ 초기화 완료\n")
    
    event = controller.last_event
    
    # 1. Scene 경계
    print(f"{'=' * 60}")
    print("1. Scene 경계 (Bounds)")
    print(f"{'=' * 60}")
    
    if 'sceneBounds' in event.metadata:
        bounds = event.metadata['sceneBounds']
        center = bounds['center']
        size = bounds['size']
        
        print(f"중심점: ({center['x']:.2f}, {center['y']:.2f}, {center['z']:.2f})")
        print(f"크기:   ({size['x']:.2f}, {size['y']:.2f}, {size['z']:.2f})")
        print(f"\n범위:")
        print(f"  X: [{center['x'] - size['x']/2:.2f}, {center['x'] + size['x']/2:.2f}]")
        print(f"  Y: [{center['y'] - size['y']/2:.2f}, {center['y'] + size['y']/2:.2f}]")
        print(f"  Z: [{center['z'] - size['z']/2:.2f}, {center['z'] + size['z']/2:.2f}]")
    else:
        print("⚠️ sceneBounds 정보 없음")
    
    # 2. 이동 가능 영역
    print(f"\n{'=' * 60}")
    print("2. 이동 가능 영역 (Reachable Positions)")
    print(f"{'=' * 60}")
    
    reachable_event = controller.step("GetReachablePositions")
    reachable_positions = reachable_event.metadata['actionReturn']
    
    if reachable_positions:
        x_coords = [p['x'] for p in reachable_positions]
        y_coords = [p['y'] for p in reachable_positions]
        z_coords = [p['z'] for p in reachable_positions]
        
        print(f"총 {len(reachable_positions)}개 위치")
        print(f"X 범위: [{min(x_coords):.2f}, {max(x_coords):.2f}]")
        print(f"Y 범위: [{min(y_coords):.2f}, {max(y_coords):.2f}]")
        print(f"Z 범위: [{min(z_coords):.2f}, {max(z_coords):.2f}]")
        
        # 샘플 위치 출력
        print(f"\n샘플 위치 (처음 5개):")
        for i, pos in enumerate(reachable_positions[:5]):
            print(f"  {i+1}. ({pos['x']:.2f}, {pos['y']:.2f}, {pos['z']:.2f})")
    else:
        print("⚠️ 이동 가능 영역 정보 없음")
    
    # 3. 객체 목록
    print(f"\n{'=' * 60}")
    print("3. Scene 내 객체 (Objects)")
    print(f"{'=' * 60}")
    
    objects = event.metadata['objects']
    
    # 객체 타입별로 그룹화
    object_types = {}
    for obj in objects:
        obj_type = obj['objectType']
        if obj_type not in object_types:
            object_types[obj_type] = []
        object_types[obj_type].append({
            'id': obj['objectId'],
            'position': obj['position'],
            'rotation': obj['rotation'],
            'visible': obj['visible'],
            'receptacle': obj.get('receptacle', False),
            'pickupable': obj.get('pickupable', False),
            'openable': obj.get('openable', False),
            'toggleable': obj.get('toggleable', False),
        })
    
    print(f"총 {len(objects)}개 객체, {len(object_types)}개 타입\n")
    
    # 타입별 개수
    print("객체 타입별 개수:")
    for obj_type, objs in sorted(object_types.items(), key=lambda x: -len(x[1])):
        print(f"  {obj_type}: {len(objs)}개")
    
    # 4. 상호작용 가능한 객체들
    print(f"\n{'=' * 60}")
    print("4. 상호작용 가능한 객체")
    print(f"{'=' * 60}")
    
    pickupable = [obj for obj in objects if obj.get('pickupable')]
    openable = [obj for obj in objects if obj.get('openable')]
    toggleable = [obj for obj in objects if obj.get('toggleable')]
    
    print(f"집을 수 있는 객체 (Pickupable): {len(pickupable)}개")
    for obj in pickupable[:5]:
        print(f"  - {obj['objectType']}: {obj['objectId']}")
    if len(pickupable) > 5:
        print(f"  ... 외 {len(pickupable) - 5}개")
    
    print(f"\n열 수 있는 객체 (Openable): {len(openable)}개")
    for obj in openable[:5]:
        print(f"  - {obj['objectType']}: {obj['objectId']}")
    if len(openable) > 5:
        print(f"  ... 외 {len(openable) - 5}개")
    
    print(f"\n토글 가능한 객체 (Toggleable): {len(toggleable)}개")
    for obj in toggleable[:5]:
        print(f"  - {obj['objectType']}: {obj['objectId']}")
    if len(toggleable) > 5:
        print(f"  ... 외 {len(toggleable) - 5}개")
    
    # 5. 특정 객체 상세 정보 (Tomato, LightSwitch)
    print(f"\n{'=' * 60}")
    print("5. 주요 객체 상세 정보")
    print(f"{'=' * 60}")
    
    for target_type in ['Tomato', 'LightSwitch', 'Fridge']:
        target_objs = [obj for obj in objects if target_type in obj['objectType']]
        if target_objs:
            print(f"\n{target_type}:")
            for obj in target_objs:
                pos = obj['position']
                rot = obj['rotation']
                print(f"  ID: {obj['objectId']}")
                print(f"  위치: ({pos['x']:.2f}, {pos['y']:.2f}, {pos['z']:.2f})")
                print(f"  회전: ({rot['x']:.2f}, {rot['y']:.2f}, {rot['z']:.2f})")
                print(f"  보임: {obj['visible']}")
                print(f"  집기 가능: {obj.get('pickupable', False)}")
                print(f"  토글 가능: {obj.get('toggleable', False)}")
                print()
    
    # JSON으로 저장
    output_data = {
        'scene': scene_name,
        'bounds': event.metadata.get('sceneBounds'),
        'reachable_positions': reachable_positions,
        'object_types': {k: len(v) for k, v in object_types.items()},
        'detailed_objects': object_types
    }
    
    output_file = f'scene_info_{scene_name}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"{'=' * 60}")
    print(f"✓ 상세 정보가 {output_file}에 저장되었습니다")
    print(f"{'=' * 60}")
    
    controller.stop()


if __name__ == "__main__":
    import sys
    
    scene = sys.argv[1] if len(sys.argv) > 1 else "FloorPlan1"
    get_detailed_scene_info(scene)
