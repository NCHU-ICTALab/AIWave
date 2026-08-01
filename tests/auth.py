from core.data.personas import PERSONAS


MEMBER_ID = PERSONAS[0].id
SECOND_MEMBER_ID = PERSONAS[1].id
THIRD_MEMBER_ID = PERSONAS[2].id

MEMBER_HEADERS = {"Authorization": "Bearer aiwave"}
SECOND_MEMBER_HEADERS = {"Authorization": "Bearer aiwave-chen"}
THIRD_MEMBER_HEADERS = {"Authorization": "Bearer aiwave-vivian"}
NEW_MEMBER_HEADERS = {"Authorization": "Bearer aiwave-new"}
PARTNER_HEADERS = {"Authorization": "Bearer aiwave-partner"}
DUSKIN_PARTNER_HEADERS = {"Authorization": "Bearer aiwave-partner-duskin"}
MANAGER_HEADERS = {"Authorization": "Bearer aiwave-manager"}
ADMIN_HEADERS = {"Authorization": "Bearer aiwave-admin"}


def with_idempotency(headers: dict[str, str], key: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": key}
