from enum import IntEnum, StrEnum


class MediaType(IntEnum):

    IMAGE = 0
    DOCUMENT = 1
    VIDEO = 2
    AUDIO = 3
    FILE = 4

class MediaCategory(StrEnum):
    
    PROFILE = "profile"
    PRODUCT = "product"
    ANIMAL = "animal"
    DOCUMENT = "document"
    ATTACHMENT = "attachment"
    BANNER = "banner"
    CATEGORY = "category"
        