from enum import Enum


class Category(str, Enum):
    HATE_SPEECH = "hate_speech"
    HARASSMENT_BULLYING = "harassment_bullying"
    VIOLENCE_INCITEMENT = "violence_incitement"
    GRAPHIC_VIOLENCE = "graphic_violence"
    SELF_HARM_SUICIDE = "self_harm_suicide"
    CSAE = "csae"
    SEXUAL_CONTENT_ADULT = "sexual_content_adult"
    TERRORISM_EXTREMISM = "terrorism_extremism"
    MISINFORMATION = "misinformation"
    SPAM_SCAM = "spam_scam"
    PII_DOXXING = "pii_doxxing"
    IP_COPYRIGHT = "ip_copyright"
    ILLEGAL_GOODS_SERVICES = "illegal_goods_services"
    REGULATED_CONTENT = "regulated_content"
    BENIGN = "benign"


class SeverityTier(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    MEDIUM_HIGH = "medium_high"
    HIGH = "high"
    CRITICAL = "critical"
