from app.services.topic_segmentation import detect_topic_divergence


def test_divergence_detection_happy_path():
    diverged, overlap, reason = detect_topic_divergence('python api auth token', '여행 일정 추천 부탁해')
    assert diverged is True
    assert reason in {'low_keyword_overlap', 'shift_expression_detected'}


def test_same_topic_keeps_segment():
    diverged, overlap, reason = detect_topic_divergence('python fastapi router', 'fastapi router에서 dependency를 어떻게 써?')
    assert diverged is False
    assert reason == 'same_topic'
