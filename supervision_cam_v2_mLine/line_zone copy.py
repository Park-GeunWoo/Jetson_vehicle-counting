import cv2
import numpy as np
from typing import Tuple, List

from data.data_store import count
from data.class_names import class_names

from supervision.tracker.byte_tracker.basetrack import TrackState

counted_tracker_ids = set()

# class LineZone:
#     def __init__(self, start: Tuple[int, int], end: Tuple[int, int]):
#         self.start = start
#         self.end = end

#     def _ccw(self, A, B, C):
#         return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

#     def is_crossing(self, prev_pos: Tuple[int, int], curr_pos: Tuple[int, int]) -> bool:
#         A, B = self.start, self.end
#         C, D = prev_pos, curr_pos
#         return self._ccw(A, C, D) != self._ccw(B, C, D) and self._ccw(A, B, C) != self._ccw(A, B, D)
# class LineZone:
#     def __init__(self, start: Tuple[int, int], end: Tuple[int, int]):
#         self.start = np.array(start)
#         self.end = np.array(end)

#     def _ccw(self, A, B, C):
#         # numpy 배열을 사용하여 연산
#         return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

#     def is_crossing(self, prev_pos: Tuple[int, int], curr_pos: Tuple[int, int]) -> bool:
#         # numpy 배열을 사용하여 이전 위치와 현재 위치 계산
#         A, B = self.start, self.end
#         C, D = np.array(prev_pos), np.array(curr_pos)
#         return self._ccw(A, C, D) != self._ccw(B, C, D) and self._ccw(A, B, C) != self._ccw(A, B, D)
class LineZone:
    def __init__(self, start: Tuple[int, int], end: Tuple[int, int]):
        self.start = np.array(start, dtype=np.float32)
        self.end = np.array(end, dtype=np.float32)
        self.direction_vector = self.end - self.start  # Precomputed direction vector

    def is_crossing(self, prev_pos: np.ndarray, curr_pos: np.ndarray) -> bool:
        """객체가 선을 교차했는지 확인하는 메서드"""
        prev_cross = np.cross(self.direction_vector, prev_pos - self.start)
        curr_cross = np.cross(self.direction_vector, curr_pos - self.start)
        # 외적의 부호가 다르면 교차한 것으로 간주
        return prev_cross * curr_cross <= 0

def process_detections(
    detections,
    tracker,
    trace_annotator,
    line_zones
):
    """
    감지된 객체의 추적 및 라인 교차 여부를 확인하는 함수.
    
    Parameters:
    - detections: 감지된 객체 목록
    - tracker: 트래커 객체
    - trace_annotator: 경로 어노테이터 객체
    - line_zones: 라인 존 객체 목록
    - check_line_crossing_multiple_zones: 라인 교차 여부를 확인하는 함수
    """
    # 감지된 객체에 대한 추적 정보 업데이트 및 라인 교차 확인
    for detection_idx in range(len(detections)):
        tracker_id = int(detections.tracker_id[detection_idx])
        x_min, y_min, x_max, y_max = detections.xyxy[detection_idx]
        center = (int((x_min + x_max) / 2), int((y_min + y_max) / 2))
        
        # 경로 업데이트
        trace_annotator.update_trace(tracker_id, center, predicted=False)
        previous_coordinates = trace_annotator.trace_data.get(tracker_id)
        # 이전 경로가 있고 길이가 2 이상일 때 라인 교차 확인
        if previous_coordinates and len(previous_coordinates) > 2:
            check_line_crossing_multiple_zones(tracker_id, previous_coordinates, line_zones)

    handle_lost_tracks(tracker, trace_annotator, line_zones)
    
    for track in tracker.removed_tracks:
        trace_annotator.remove_trace(track.external_track_id)

    labels = [
        f"#{tracker_id} {class_names.get(class_id, 'Unknown')} {confidence:.2f}" 
        for tracker_id, class_id, confidence in zip(
            detections.tracker_id, detections.class_id, detections.confidence
        )
    ]
    return labels


def handle_lost_tracks(tracker, trace_annotator, line_zones):
    """잃어버린 객체에 대한 추적 정보 처리"""
    for track in tracker.lost_tracks:
        if track.state == TrackState.Lost:
            predicted_coords = track.mean[:2]
            center = (int(predicted_coords[0]), int(predicted_coords[1]))
            # 경로 업데이트 (예측된 좌표로)
            trace_annotator.update_trace(track.external_track_id, center, predicted=True)
            previous_coordinates = trace_annotator.trace_data.get(track.external_track_id)
            # 이전 경로가 있고 길이가 2 이상일 때 라인 교차 확인
            if previous_coordinates and len(previous_coordinates) > 2:
                check_line_crossing_multiple_zones(track.external_track_id, previous_coordinates, line_zones)


def check_line_crossing_multiple_zones(tracker_id: int, previous_coordinates: list, line_zones: list):
    """여러 LineZone과 교차 여부를 확인하는 함수"""
    if tracker_id in counted_tracker_ids:
        return

    global count
    
    prev_coords = np.array(previous_coordinates[-3][0])
    curr_coords = np.array(previous_coordinates[-1][0])

    for line_zone in line_zones:
        # 객체가 교차했는지 확인
        if line_zone.is_crossing(prev_coords, curr_coords):
            # 이전 위치와 현재 위치 방향 계산
            #외적 값이 양수: 선의 왼쪽에 있음
            #외적 값이 음수: 선의 오른쪽에 있음
            curr_direction = -np.cross(line_zone.direction_vector, curr_coords - line_zone.start)
            prev_direction = -np.cross(line_zone.direction_vector, prev_coords - line_zone.start)
            # 이전 방향과 현재 방향이 다르면 교차
            if prev_direction > 0 and curr_direction <= 0:
                count[0] += 1
                counted_tracker_ids.add(tracker_id)
                break
