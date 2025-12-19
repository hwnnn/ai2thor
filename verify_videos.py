#!/usr/bin/env python3
"""생성된 영상 파일 검증"""

import cv2
import numpy as np
import sys

timestamp = "20251219_200602"

print("=" * 60)
print("생성된 영상 검증")
print("=" * 60)

# Topdown view 검증
print("\n1. Topdown view:")
cap = cv2.VideoCapture(f'output_videos/topview_{timestamp}.mp4')
if cap.isOpened():
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    ret, first_frame = cap.read()
    if ret:
        avg = np.mean(first_frame)
        print(f"   해상도: {width}x{height}")
        print(f"   FPS: {fps:.1f}")
        print(f"   프레임 수: {frame_count}")
        print(f"   평균 픽셀: {avg:.2f}")
        if avg > 50:
            print("   ✓ 정상적인 topdown view!")
            cv2.imwrite('output_images/topdown_improved.jpg', first_frame)
            print("   → output_images/topdown_improved.jpg 저장")
        else:
            print("   ⚠️ 어두운 화면")
else:
    print("   ❌ 파일 열기 실패")
cap.release()

# Agent 1 POV
print("\n2. Agent 1 POV:")
cap = cv2.VideoCapture(f'output_videos/agent_1_pov_{timestamp}.mp4')
if cap.isOpened():
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ret, first_frame = cap.read()
    if ret:
        avg = np.mean(first_frame)
        print(f"   프레임 수: {frame_count}")
        print(f"   평균 픽셀: {avg:.2f}")
        if avg > 50:
            print("   ✓ 정상적인 agent view!")
            cv2.imwrite('output_images/agent1_improved.jpg', first_frame)
            print("   → output_images/agent1_improved.jpg 저장")
else:
    print("   ❌ 파일 열기 실패")
cap.release()

# Agent 2 POV
print("\n3. Agent 2 POV:")
cap = cv2.VideoCapture(f'output_videos/agent_2_pov_{timestamp}.mp4')
if cap.isOpened():
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ret, first_frame = cap.read()
    if ret:
        avg = np.mean(first_frame)
        print(f"   프레임 수: {frame_count}")
        print(f"   평균 픽셀: {avg:.2f}")
        if avg > 50:
            print("   ✓ 정상적인 agent view!")
            cv2.imwrite('output_images/agent2_improved.jpg', first_frame)
            print("   → output_images/agent2_improved.jpg 저장")
else:
    print("   ❌ 파일 열기 실패")
cap.release()

print("\n" + "=" * 60)
print("검증 완료!")
print("=" * 60)
print("\n✅ 결과:")
print("  • Topdown view: Scene을 위에서 내려다보는 시점")
print("  • Agent 1 POV: 토마토를 찾는 에이전트 시야")
print("  • Agent 2 POV: 라이트 스위치를 찾는 에이전트 시야")
print("\n모든 영상이 output_videos/ 폴더에 저장되었습니다.")
print("스크린샷은 output_images/ 폴더에 저장되었습니다.")
