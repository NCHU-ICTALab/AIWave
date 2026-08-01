"""把官方對齊的題組模型序列化成 Web 可直接渲染的表單定義。

內部模型忠於官方 `pms_form_*` schema；此層只做呈現轉換，讓前端不必認識官方欄位。
日期題的 `start/end_date_offset_days`（相對偏移）在這裡換算成絕對日期，前端拿到就能用。
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import Form, Topic, TopicType
from .service_catalog import ServiceInfo


def service_to_dict(service: ServiceInfo) -> dict:
    return {
        "id": service.id,
        "name": service.name,
        "category": service.category,
        "summary": service.summary,
        "partner": service.partner,
        "glyph": service.glyph,
        "keywords": list(service.search_terms),
    }


def _visible_when(form: Form, topic: Topic) -> dict | None:
    """把 option-id 為基礎的跳題規則，轉成前端用的 {fieldId, equals} 值。"""
    rule = topic.skip_logic
    if rule is None:
        return None
    source = form.topic(rule.topic_id)
    if source is None:
        return None
    values = [
        option.value or str(option.id)
        for option_id in rule.answer_in
        if (option := source.option(option_id)) is not None
    ]
    if not values:
        return None
    return {"fieldId": source.field_key, "equals": values[0]}


def _field_to_dict(form: Form, topic: Topic, today: date) -> dict:
    field: dict = {
        "id": topic.field_key,
        "topicId": topic.id,
        "label": topic.title,
        "type": int(topic.type.value),
        "required": topic.is_required,
    }
    if topic.hint:
        field["hint"] = topic.hint
    if topic.is_number_only:
        field["numberOnly"] = True
    if topic.min_value is not None:
        field["min"] = topic.min_value
    if topic.max_value is not None:
        field["max"] = topic.max_value
    if topic.type is TopicType.DATE:
        if topic.start_date_offset_days is not None:
            field["minDate"] = (today + timedelta(days=topic.start_date_offset_days)).isoformat()
        if topic.end_date_offset_days is not None:
            field["maxDate"] = (today + timedelta(days=topic.end_date_offset_days)).isoformat()
    if topic.options:
        field["options"] = [
            {
                "value": option.value or str(option.id),
                "label": option.option_name,
                "optionId": option.id,
            }
            for option in topic.options
            if option.parent_id is None
        ]
    if (rule := _visible_when(form, topic)) is not None:
        field["visibleWhen"] = rule
    return field


def summarize_feedback(form: Form, feedback_content: dict) -> list[dict]:
    """把官方 answerList 轉成「題目：答案」的可讀摘要，供廠商與住戶檢視。"""
    summary: list[dict] = []
    for entry in feedback_content.get("data", []):
        topic = form.topic(entry.get("topicId"))
        if topic is None:
            continue
        values: list[str] = []
        for answer in entry.get("answerList", []):
            if answer.get("answer") is not None:
                quantity = f"×{answer['quantity']}" if answer.get("quantity") else ""
                values.append(f"{answer['answer']}{quantity}")
            elif answer.get("districtName"):
                values.append(f"{answer.get('countyName') or ''}{answer['districtName']}")
            elif answer.get("imgUrl"):
                values.append(f"{len(answer['imgUrl'])} 張照片")
            elif answer.get("name"):
                contact = f"{answer.get('name')} {answer.get('mobile', '')}".strip()
                if answer.get("address"):
                    contact += f"・{answer['address']}"
                values.append(contact)
        if values:
            summary.append({"label": topic.title, "value": "、".join(values)})
    return summary


def topic_to_field(form: Form, topic: Topic, *, today: date) -> dict:
    """單一題目的可渲染表示——讓對話介面能把選項畫成按鈕，而不是要使用者打字。"""
    return _field_to_dict(form, topic, today)


def form_to_dict(form: Form, *, today: date) -> dict:
    """序列化成前端 `ServiceFormDefinition` 的形狀。"""
    return {
        "serviceId": form.service_id,
        "formId": form.id,
        "action": form.action.value,
        "actionLabel": form.action_label,
        "dataUse": form.data_use,
        "fields": [_field_to_dict(form, topic, today) for topic in form.ordered_topics()],
    }
