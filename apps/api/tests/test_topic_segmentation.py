from app.services.topic_segmentation import detect_topic_divergence


def test_divergence_detection_happy_path():
    diverged, overlap, reason, action = detect_topic_divergence('python api auth token', '여행 일정 추천 부탁해', 'python backend auth')
    assert diverged is True
    assert action == 'new_segment'
    assert reason in {'low_overlap_with_segment', 'shift_expression_detected'}


def test_same_topic_keeps_segment():
    diverged, overlap, reason, action = detect_topic_divergence('python fastapi router', 'fastapi router에서 dependency를 어떻게 써?', 'fastapi router summary')
    assert diverged is False
    assert action == 'stay'
    assert reason in {'same_topic', 'short_input_fallback'}
