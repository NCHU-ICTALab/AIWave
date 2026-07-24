"""題組引擎測試（確定性核心，不接 LLM/DB）。"""

from __future__ import annotations

from datetime import date

import pytest

from core.forms import FormError, FormSession, Selection
from core.forms.seed_forms import (
    OPT_AC_SPLIT,
    OPT_AC_WASH,
    OPT_LAMP_OFF,
    OPT_MST_UNCLOG,
    OPT_SOCKET,
    facility_form,
    group_buy_form,
    repair_form,
)

TODAY = date(2026, 7, 24)


# ---- 流程與跳題 --------------------------------------------------------

def test_first_topic_is_repair_items():
    s = FormSession(repair_form())
    nxt = s.next_topic()
    assert nxt is not None and nxt.id == 1 and nxt.title == "需要修繕的項目"


def test_skip_ac_type_when_not_choosing_ac():
    """沒選冷氣清洗 → 跳過「冷氣型式」，直接到照片題。"""
    s = FormSession(repair_form())
    nxt = s.submit_answer(1, OPT_LAMP_OFF)  # 只修燈具
    assert nxt is not None and nxt.id == 3  # 跳過 id=2 冷氣型式
    assert s.form.topic(2) is not None
    assert not s.is_visible(s.form.topic(2))  # 冷氣型式不可見


def test_ask_ac_type_when_choosing_ac():
    """選了冷氣清洗（含台數）→ 追問「冷氣型式」。"""
    s = FormSession(repair_form())
    nxt = s.submit_answer(1, Selection(option_id=OPT_AC_WASH, quantity=2))
    assert nxt is not None and nxt.id == 2 and nxt.title == "冷氣型式"


def test_submitting_hidden_topic_raises():
    s = FormSession(repair_form())
    s.submit_answer(1, OPT_SOCKET)  # 插座，未選冷氣
    with pytest.raises(FormError):
        s.submit_answer(2, OPT_AC_SPLIT)  # 冷氣型式此時不該出現


def test_progress_counts_explicit_optional_skip() -> None:
    session = FormSession(repair_form())
    session.submit_answer(1, OPT_SOCKET)
    session.skip(3)
    assert session.progress() == {"answered": 2, "total": 6}


# ---- 驗證 --------------------------------------------------------------

def test_quantity_required_and_bounded():
    s = FormSession(repair_form())
    with pytest.raises(FormError):
        s.submit_answer(1, OPT_AC_WASH)  # 冷氣清洗需填台數
    with pytest.raises(FormError):
        s.submit_answer(1, Selection(option_id=OPT_AC_WASH, quantity=9))  # 超過 max 5


def test_unknown_option_rejected():
    s = FormSession(repair_form())
    with pytest.raises(FormError):
        s.submit_answer(1, 999)


def test_required_text_and_number_only():
    s = facility_form()
    sess = FormSession(s, today=TODAY)
    sess.submit_answer(1, 301)                 # 交誼廳
    sess.submit_answer(2, "2026-07-25")        # 明天
    sess.submit_answer(3, 311)                 # 上午
    with pytest.raises(FormError):
        sess.submit_answer(4, "兩人")          # 人數限數字


def test_single_choice_rejects_multiple():
    sess = FormSession(facility_form(), today=TODAY)
    with pytest.raises(FormError):
        sess.submit_answer(1, [301, 302])  # 公設為單選


def test_date_range_enforced_with_today():
    sess = FormSession(facility_form(), today=TODAY)
    sess.submit_answer(1, 301)
    with pytest.raises(FormError):
        sess.submit_answer(2, "2026-08-30")  # 超過 today+7
    with pytest.raises(FormError):
        sess.submit_answer(2, "2026-07-25 上午")  # 格式錯


# ---- 完成與輸出 --------------------------------------------------------

def _fill_repair(sess: FormSession) -> FormSession:
    sess.submit_answer(1, [
        Selection(option_id=OPT_MST_UNCLOG),
        Selection(option_id=OPT_AC_WASH, quantity=2),
    ])
    sess.submit_answer(2, OPT_AC_SPLIT)
    sess.submit_answer(4, {"county_code": "01", "district_code": "002",
                           "county_name": "台北市", "district_name": "大同區"})
    sess.submit_answer(5, "2026-07-28")
    sess.submit_answer(6, 161)
    sess.submit_answer(7, {"name": "陳阿姨", "mobile": "0912345678"})
    return sess


def test_not_complete_until_required_done():
    sess = FormSession(repair_form(), today=TODAY)
    sess.submit_answer(1, OPT_SOCKET)
    assert not sess.is_complete()


def test_complete_flow_and_feedback_content():
    sess = _fill_repair(FormSession(repair_form(), today=TODAY))
    # 必填全數答完 → 完成；但選填的照片題仍會被提出（完成 ≠ 沒有可選題）
    assert sess.is_complete()
    remaining = sess.next_topic()
    assert remaining is not None and remaining.id == 3 and not remaining.is_required

    fc = sess.to_feedback_content()
    data = fc["data"]
    by_topic = {d["topicId"]: d for d in data}

    # 照片題（id=3，選填未答）不應出現在輸出
    assert 3 not in by_topic
    # 複選題輸出：雙層子選項的 answer 應是「父-子」，且帶數量
    q1 = by_topic[1]
    assert q1["type"] == "4"
    answers = {a["answerId"]: a for a in q1["answerList"]}
    assert answers[OPT_MST_UNCLOG]["answer"] == "馬桶-不通"
    assert answers[OPT_AC_WASH]["quantity"] == 2
    # 地區題輸出
    q4 = by_topic[4]
    assert q4["answerList"][0]["countyCode"] == "01"
    assert q4["answerList"][0]["districtName"] == "大同區"
    # 日期題輸出
    assert by_topic[5]["answerList"][0]["answer"] == "2026-07-28"


def test_skip_optional_then_reach_required():
    """略過選填照片題後，能繼續走到後面的必填題。"""
    sess = FormSession(repair_form(), today=TODAY)
    sess.submit_answer(1, OPT_SOCKET)   # 插座（不觸發冷氣型式）
    assert sess.next_topic().id == 3    # 選填照片
    nxt = sess.skip(3)
    assert nxt is not None and nxt.id == 4  # 續到必填的服務地址
    with pytest.raises(FormError):
        sess.skip(4)                    # 必填不可略過


def test_known_answers_prefilled_and_skipped():
    """聯絡資料由 resident 帶入 → 不再是下一題。"""
    sess = FormSession(
        group_buy_form(item_name="愛文芒果", max_qty=5),
        known={3: {"name": "林先生", "mobile": "0900000000"}},
    )
    sess.submit_answer(1, Selection(option_id=201, quantity=2))
    nxt = sess.submit_answer(2, 211)  # 取貨方式→管理室
    assert nxt is None  # 聯絡資料已帶入，全部完成
    assert sess.is_complete()
