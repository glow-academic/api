"""Module 03 — Model seed definitions.

Each dict maps directly to CreateModelItem fields.
String fields (name, description) are resolved by the _impl function.
"""

from uuid import UUID

from database.seeds.providers import GEMINI, OPENAI

# ---------------------------------------------------------------------------
# Provider resource IDs from existing SQL (mapped to seed constants)
# When created via _impl, artifact ID = resource ID, so we use
# the provider constants directly.
# ---------------------------------------------------------------------------

_PROVIDER = {
    "openai": OPENAI,
    "gemini": GEMINI,
}

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by other modules
# ---------------------------------------------------------------------------

GEMINI_2_5_FLASH_IMAGE = UUID("019b3be4-36d1-77e9-a142-1caa685eefb0")
GEMINI_2_5_FLASH_LITE = UUID("019b3be4-36cd-7877-836a-8a5fc9b7f7bb")
GEMINI_2_5_FLASH = UUID("019b3be4-36cd-7821-9ad2-6c260f8271b9")
GEMINI_2_5_PRO = UUID("019b3be4-36cd-7883-b878-cf77e61f5906")
GEMINI_3_PRO_IMAGE_PREVIEW = UUID("019b3be4-36d1-77f4-ae69-94e974529f3d")
GEMINI_3_PRO_PREVIEW = UUID("019b3be4-36d1-77ac-9c8d-7bcd806fbcf7")
IMAGEN_4_0_FAST_GENERATE_001 = UUID("019b3be4-36d1-782b-9f07-7b368cadc1f1")
IMAGEN_4_0_GENERATE_001 = UUID("019b3be4-36d1-781d-9346-a9a8e2d4306d")
IMAGEN_4_0_ULTRA_GENERATE_001 = UUID("019b3be4-36d1-7837-84df-b45edebc4ee5")
VEO_3_1_FAST_GENERATE_PREVIEW = UUID("019b3be4-36d1-7811-8a78-2a54d6facafc")
VEO_3_1_GENERATE_PREVIEW = UUID("019b3be4-36d1-7805-8d8b-9c811e4e765b")
GPT_4_1 = UUID("019b3be4-36cd-7888-842b-8c6f8dfb363b")
GPT_5_MINI = UUID("019b3be4-36d1-7742-89d5-a4dabeba6ae3")
GPT_5_NANO = UUID("019b3be4-36d1-7753-88ba-93ca9b8c6ee5")
GPT_5_1 = UUID("019b3be4-36d1-7790-ae43-d83841b86f0b")
GPT_5 = UUID("019b3be4-36d1-7723-9b2e-5ea00d22ad62")
GPT_AUDIO_MINI = UUID("019b3be4-36d1-77d1-bf3d-f2920b175b97")
GPT_AUDIO = UUID("019b3be4-36d1-77bb-b61a-400ca2e43b82")
GPT_IMAGE_1_MINI = UUID("019b3be4-36d1-786c-a2d6-39d1847d758c")
GPT_IMAGE_1 = UUID("019b3be4-36d1-785a-afe5-6f3a911cdf01")
GPT_OSS_20B = UUID("019b3be4-36cd-7891-988a-33c18c46a564")
GPT_REALTIME_MINI = UUID("019b3be4-36d1-77dc-8a0c-81273114cb56")
GPT_REALTIME = UUID("019b3be4-36d1-776a-8c68-59e8e40a6e77")
SORA_2_PRO = UUID("019b3be4-36d1-7887-a4a4-c282641fe9e3")
SORA_2 = UUID("019b3be4-36d1-7777-ad9f-cbe6aa668517")

# ---------------------------------------------------------------------------
# Shared temperature level sets (101 levels from 0.0 to 1.0)
# ---------------------------------------------------------------------------

_TEMP_LEVELS_FULL = [
    UUID("019c441a-0e9e-7bef-841d-5d33999c9d12"),
    UUID("019c441a-0e9e-7c74-928c-7c0739193aff"),
    UUID("019c441a-0e9e-7c9e-8acc-69725eead5b3"),
    UUID("019c441a-0e9e-7ca4-ad96-a64b4ddb14b4"),
    UUID("019c441a-0e9e-7cc4-83a2-f576e1eac21e"),
    UUID("019c441a-0e9e-7cd3-9f45-b7f2ddd50383"),
    UUID("019c441a-0e9e-7cdc-b2f0-1daefbf9a0d2"),
    UUID("019c441a-0e9e-7ce6-a3df-5d1581d924f8"),
    UUID("019c441a-0e9e-7cf7-b9c2-b296333b30ee"),
    UUID("019c441a-0e9e-7d1a-9b3d-4b030af5a5f5"),
    UUID("019c441a-0e9e-7d22-aa42-b094ce03c315"),
    UUID("019c441a-0e9e-7d2d-a122-d5e27a709e64"),
    UUID("019c441a-0e9e-7d34-beaf-cb977faaad88"),
    UUID("019c441a-0e9e-7d59-bd04-7501bbcf1b85"),
    UUID("019c441a-0e9e-7d84-b9a5-aa946d36a18d"),
    UUID("019c441a-0e9e-7d9e-b960-c7edff5d9bce"),
    UUID("019c441a-0e9e-7da6-ae62-6e2a16407f9d"),
    UUID("019c441a-0e9e-7db9-b0f3-8d485af3cc59"),
    UUID("019c441a-0e9e-7dcd-be35-3ab6d31cfb17"),
    UUID("019c441a-0e9e-7dd6-b25d-1fa87885be16"),
    UUID("019c441a-0e9e-7dde-a7b4-fa61b030af17"),
    UUID("019c441a-0e9e-7dfb-9078-f1a2807595ff"),
    UUID("019c441a-0e9e-7e0e-93ba-b9080f53300b"),
    UUID("019c441a-0e9e-7e19-89e1-76a54e0e513b"),
    UUID("019c441a-0e9e-7e2b-91ce-0aadfc9baef7"),
    UUID("019c441a-0e9e-7e37-a9f8-4388d8363acc"),
    UUID("019c441a-0e9e-7e3d-b9e4-8df4302ca526"),
    UUID("019c441a-0e9e-7e52-b580-9218337e5382"),
    UUID("019c441a-0e9e-7e5a-933e-d1c96ab450fe"),
    UUID("019c441a-0e9e-7e62-b187-072e351576b7"),
    UUID("019c441a-0e9e-7e69-a60a-627a1928dda8"),
    UUID("019c441a-0e9e-7e73-ab7c-6b05701f3683"),
    UUID("019c441a-0e9e-7e89-8b78-5a89a8ee38df"),
    UUID("019c441a-0e9e-7e94-9c38-b7f44e86a101"),
    UUID("019c441a-0e9e-7ea0-afe1-143d03e99a25"),
    UUID("019c441a-0e9e-7eb0-ba12-fa36a878cdef"),
    UUID("019c441a-0e9e-7ebf-83f0-e822b230d010"),
    UUID("019c441a-0e9e-7ec9-8819-23cf95608dbe"),
    UUID("019c441a-0e9e-7ed1-9766-04be0f1c6b20"),
    UUID("019c441a-0e9e-7ede-ab08-a9ec02a3d29f"),
    UUID("019c441a-0e9e-7ef6-8811-b13973658720"),
    UUID("019c441a-0e9e-7f0d-9e4b-4b564ec66598"),
    UUID("019c441a-0e9e-7f26-8ca6-a1b33fb97fbe"),
    UUID("019c441a-0e9e-7f2e-81d2-2545ba70f21d"),
    UUID("019c441a-0e9e-7f44-bb0b-5190a35cc0c0"),
    UUID("019c441a-0e9e-7f53-8a08-d51406e55622"),
    UUID("019c441a-0e9e-7f5f-9e3d-9922fdb0fdff"),
    UUID("019c441a-0e9e-7f6c-a798-8328630ab038"),
    UUID("019c441a-0e9e-7f80-a9cb-7b1c947ad4c8"),
    UUID("019c441a-0e9e-7f8f-b0cf-ab7d52866f69"),
    UUID("019c441a-0e9e-7fa5-87e8-3e52d48647cd"),
    UUID("019c441a-0e9e-7fae-bed9-1177ce0bd598"),
    UUID("019c441a-0e9e-7fbb-84b9-a7962089afa4"),
    UUID("019c441a-0e9e-7fc1-8cef-8914d6b01390"),
    UUID("019c441a-0e9e-7fcd-afc7-37cf75ba25a7"),
    UUID("019c441a-0e9e-7fde-a372-d6c53b939a2d"),
    UUID("019c441a-0e9e-7fee-be99-7292d6d5e130"),
    UUID("019c441a-0e9e-7ff9-8627-a980b71f8514"),
    UUID("019c441a-0e9f-7004-9320-7d40cf5cd428"),
    UUID("019c441a-0e9f-700c-a8c5-11434dc2ea95"),
    UUID("019c441a-0e9f-7016-9973-59eca073bebe"),
    UUID("019c441a-0e9f-7027-b2b3-40f7679aa440"),
    UUID("019c441a-0e9f-7038-a8fe-a960af92c6cd"),
    UUID("019c441a-0e9f-7055-8c67-a6f96ebb872b"),
    UUID("019c441a-0e9f-7067-a9d9-66f6b22a620c"),
    UUID("019c441a-0e9f-7076-b0f4-d3db8a59a2bf"),
    UUID("019c441a-0e9f-7087-a7c2-481e3cf67900"),
    UUID("019c441a-0e9f-708c-ace6-6ab6bfb9032b"),
    UUID("019c441a-0e9f-70a7-8312-c8913b2bd033"),
    UUID("019c441a-0e9f-70b3-bad8-286a24dc5f49"),
    UUID("019c441a-0e9f-70be-928f-7873d52a9642"),
    UUID("019c441a-0e9f-70ce-849a-af4b11bbfaf6"),
    UUID("019c441a-0e9f-70d9-8046-2d636f526116"),
    UUID("019c441a-0e9f-70e8-8235-7196b41406e1"),
    UUID("019c441a-0e9f-70f0-a568-30584bfef8fb"),
    UUID("019c441a-0e9f-7101-afd8-b2e50bc968f9"),
    UUID("019c441a-0e9f-710b-99b2-3db575f01df1"),
    UUID("019c441a-0e9f-7116-ab87-05d7035642c7"),
    UUID("019c441a-0e9f-7120-bc1c-1e290802109a"),
    UUID("019c441a-0e9f-712f-ad29-33e6889ca042"),
    UUID("019c441a-0e9f-713c-87f4-1ce375f0e09f"),
    UUID("019c441a-0e9f-715a-8037-ac5450f006cb"),
    UUID("019c441a-0e9f-7166-a4b2-8eef873a73e7"),
    UUID("019c441a-0e9f-716f-9341-e1c1d078369b"),
    UUID("019c441a-0e9f-7176-a9ff-74d14b50e469"),
    UUID("019c441a-0e9f-718b-9bf3-c0143fa5d3c1"),
    UUID("019c441a-0e9f-732f-ac4d-b10174e69e21"),
    UUID("019c441a-0e9f-7335-a559-31fe7e8db595"),
    UUID("019c441a-0e9f-735a-81cf-eed6e8196398"),
    UUID("019c441a-0e9f-7370-856d-7b31ced06c90"),
    UUID("019c441a-0e9f-738a-9c75-c3dc21a1aed4"),
    UUID("019c441a-0e9f-73a7-8628-636b0586d4fb"),
    UUID("019c441a-0e9f-73b3-b4c6-96f71113e8dc"),
    UUID("019c441a-0e9f-73b7-a591-e6cb67cc219a"),
    UUID("019c441a-0e9f-73ca-8872-97569ea04c56"),
    UUID("019c441a-0e9f-73d9-a939-23bb7a0cc094"),
    UUID("019c441a-0e9f-73e9-9074-5fc628f2e51c"),
    UUID("019c441a-0e9f-73f9-b1ae-e42dda0fd3c5"),
    UUID("019c441a-0e9f-7413-be9e-8c771dd1ceb2"),
    UUID("019c441a-0e9f-741c-889d-c67c16f9dc2b"),
    UUID("019c441a-0e9f-742a-995a-2c0c8e1cffba"),
]

# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------

models = [
    dict(
        id=GEMINI_2_5_FLASH_IMAGE,
        name="gemini-2.5-flash-image",
        description="Gemini 2.5 Flash Image is Google's native image generation model, optimized for speed, flexibility, and contextual understanding. Text input and output is priced the same as 2.5 Flash.",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e616-7639-bdef-fe85d318ea5d"),
            UUID("019bbce5-e613-7123-884c-ce90a613ecfa"),
        ],
    ),
    dict(
        id=GEMINI_2_5_FLASH_LITE,
        name="gemini-2.5-flash-lite",
        description="Gemini 2.5 Flash Lite is a lightweight version of Gemini 2.5 Flash optimized for speed and efficiency.",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75df-923a-6b23040e63b3"),
            UUID("019c47d6-6c45-75ed-b882-53a18d4f5db6"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e617-7969-b29c-8518b3ecfa80"),
            UUID("019bbce5-e612-765b-9c4b-1f5257b9de29"),
        ],
        reasoning_level_ids=[
            UUID("019bb58e-0ae0-74a2-a7dc-b32fdb4ce93c"),
            UUID("019bb58e-0ae0-7520-9f94-46c300d57c63"),
            UUID("019bb58e-0ae0-73e4-943f-60951f322d0a"),
            UUID("019bb58e-0ae0-756a-9627-e068af5f7478"),
        ],
        # 101 temperature levels — see _TEMP_LEVELS_FULL below
        temperature_level_ids=_TEMP_LEVELS_FULL,
    ),
    dict(
        id=GEMINI_2_5_FLASH,
        name="gemini-2.5-flash",
        description="Gemini 2.5 Flash is a language model that can be used to generate text, images, and audio. Pricing shown is for thinking mode.",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75df-923a-6b23040e63b3"),
            UUID("019c47d6-6c45-75ed-b882-53a18d4f5db6"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e618-7571-925a-803f2089d71b"),
            UUID("019bbce5-e613-7123-884c-ce90a613ecfa"),
        ],
        reasoning_level_ids=[
            UUID("019bb58e-0ae0-7260-a3ce-a897fd08a421"),
            UUID("019bb58e-0ae0-732c-b10b-04ed0a31f86a"),
            UUID("019bb58e-0adf-7b5a-8e46-40a6c1b8dc9a"),
            UUID("019bb58e-0ae0-7188-94e0-c678dc587ef4"),
        ],
        # 101 temperature levels — see _TEMP_LEVELS_FULL below
        temperature_level_ids=_TEMP_LEVELS_FULL,
    ),
    dict(
        id=GEMINI_2_5_PRO,
        name="gemini-2.5-pro",
        description="Gemini 2.5 Pro is Google's most advanced language model with enhanced reasoning and multimodal capabilities. Pricing shown is for context windows ≤200k tokens.",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75df-923a-6b23040e63b3"),
            UUID("019c47d6-6c45-75ed-b882-53a18d4f5db6"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e619-71a6-805e-be8916a1565e"),
            UUID("019bbce5-e618-7cbd-ba98-7b0d3adc15b3"),
            UUID("019bbce5-e614-7dba-bfc7-104348e5a45e"),
            UUID("019bbce5-e613-7f49-90e2-722d3188bb30"),
        ],
    ),
    dict(
        id=GEMINI_3_PRO_IMAGE_PREVIEW,
        name="gemini-3-pro-image-preview",
        description="Gemini 3 Pro Image Preview is Google's native image generation model, optimized for speed, flexibility, and contextual understanding. Text input and output is priced the same as Gemini 3 Pro.",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e61a-7134-b388-56de1664ed02"),
            UUID("019bbce5-e619-7977-98d3-a5f86433086f"),
            UUID("019bbce5-e618-7f1b-821b-25d03479409c"),
            UUID("019bbce5-e614-71cb-9535-84cdb7eac6ea"),
        ],
    ),
    dict(
        id=GEMINI_3_PRO_PREVIEW,
        name="gemini-3-pro-preview",
        description="Gemini 3 Pro Preview is Google's most advanced language model. Pricing shown is for prompts ≤200k tokens. Separate higher tier for prompts >200k (input $4 / output $18 / cache $0.40).",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75df-923a-6b23040e63b3"),
            UUID("019c47d6-6c45-75ed-b882-53a18d4f5db6"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e619-7977-98d3-a5f86433086f"),
            UUID("019bbce5-e618-7f1b-821b-25d03479409c"),
            UUID("019bbce5-e615-7039-9e54-d02b6e278e6e"),
            UUID("019bbce5-e614-7b0a-9775-52f849776328"),
        ],
        reasoning_level_ids=[
            UUID("019bb58e-0ae0-7878-af71-36c0539cb08c"),
            UUID("019bb58e-0ae0-78fe-99ef-e2f3db093a78"),
            UUID("019bb58e-0ae0-78bd-98c8-090192eb67b6"),
            UUID("019bb58e-0ae0-783a-973f-1b00cee18340"),
        ],
        # 101 temperature levels — see _TEMP_LEVELS_FULL below
        temperature_level_ids=_TEMP_LEVELS_FULL,
    ),
    dict(
        id=IMAGEN_4_0_FAST_GENERATE_001,
        name="imagen-4.0-fast-generate-001",
        description="Imagen 4 Fast - Faster variant of Imagen 4 image generation model",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
        ],
        pricing_ids=[
            UUID("019bbce5-e616-7183-ba48-82eb73b11c6d"),
        ],
    ),
    dict(
        id=IMAGEN_4_0_GENERATE_001,
        name="imagen-4.0-generate-001",
        description="Imagen 4 Standard - Latest image generation model with significantly better text rendering and overall image quality",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
        ],
        pricing_ids=[
            UUID("019bbce5-e616-78c7-98da-9323f8fbe9c0"),
        ],
    ),
    dict(
        id=IMAGEN_4_0_ULTRA_GENERATE_001,
        name="imagen-4.0-ultra-generate-001",
        description="Imagen 4 Ultra - Highest quality variant of Imagen 4 image generation model",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
        ],
        pricing_ids=[
            UUID("019bbce5-e616-7d80-9151-67a90c90a6a2"),
        ],
    ),
    dict(
        id=VEO_3_1_FAST_GENERATE_PREVIEW,
        name="veo-3.1-fast-generate-preview",
        description="Veo 3.1 Fast - Faster variant of Veo 3.1 video generation model",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e608-7d5a-b937-0a22697e3f8b"),
            UUID("019bbce5-e607-7bc4-a6b0-a4218bc8e5f8"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
        ],
        pricing_ids=[
            UUID("019bbce5-e617-722a-9bd2-66a46aff5385"),
        ],
    ),
    dict(
        id=VEO_3_1_GENERATE_PREVIEW,
        name="veo-3.1-generate-preview",
        description="Veo 3.1 Standard - Our latest video generation model, generates video with audio from text and image prompts",
        provider_ids=[_PROVIDER["gemini"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e608-7d5a-b937-0a22697e3f8b"),
            UUID("019bbce5-e607-7bc4-a6b0-a4218bc8e5f8"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
        ],
        pricing_ids=[
            UUID("019bbce5-e617-7bcd-89ad-641e506e5954"),
        ],
    ),
    dict(
        id=GPT_4_1,
        name="gpt-4.1",
        description="GPT-4.1 excels at instruction following and tool calling, with broad knowledge across domains. It features a 1M token context window, and low latency without a reasoning step.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e61c-72ba-80a6-0f8c95e0db6c"),
            UUID("019bbce5-e618-7805-9dd6-e845d173a27f"),
            UUID("019bbce5-e614-71cb-9535-84cdb7eac6ea"),
        ],
        # 101 temperature levels — see _TEMP_LEVELS_FULL below
        temperature_level_ids=_TEMP_LEVELS_FULL,
    ),
    dict(
        id=GPT_5_MINI,
        name="gpt-5-mini",
        description="GPT-5 Mini is a faster, more efficient version of GPT-5 optimized for speed and cost.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e618-70bf-a5a0-4af9f941f075"),
            UUID("019bbce5-e61b-77d4-952b-29ed47b20942"),
            UUID("019bbce5-e612-7bea-a6df-af5f0f5aeaef"),
        ],
    ),
    dict(
        id=GPT_5_NANO,
        name="gpt-5-nano",
        description="GPT-5 Nano is the smallest and fastest GPT-5 variant, ideal for real-time applications.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e617-7969-b29c-8518b3ecfa80"),
            UUID("019bbce5-e61b-751b-8ec3-984992180842"),
            UUID("019bbce5-e612-70a7-ab5c-535d4ec6d3c1"),
        ],
    ),
    dict(
        id=GPT_5_1,
        name="gpt-5.1",
        description="GPT-5.1 is OpenAI's latest language model with advanced reasoning and multimodal capabilities. 400k context, 128k max output.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e61b-7e7f-b6cb-6d52b3735329"),
            UUID("019bbce5-e618-7a61-8daf-07ca0f11f252"),
            UUID("019bbce5-e613-7cce-9e54-d93870e9ceb0"),
        ],
        reasoning_level_ids=[
            UUID("019bb58e-0ae0-7737-8da3-d47217886e42"),
            UUID("019bb58e-0ae0-777a-ac31-d4a94d6b1e43"),
            UUID("019bb58e-0ae0-77bb-9ef5-38d4d3963794"),
            UUID("019bb58e-0ae0-76f4-8dc9-ffa189134ba4"),
            UUID("019bb58e-0ae0-77f9-93e1-a6688660a4d6"),
        ],
        # 101 temperature levels — see _TEMP_LEVELS_FULL below
        temperature_level_ids=_TEMP_LEVELS_FULL,
    ),
    dict(
        id=GPT_5,
        name="gpt-5",
        description="GPT-5 is OpenAI's latest language model with advanced reasoning and multimodal capabilities.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e61b-7e7f-b6cb-6d52b3735329"),
            UUID("019bbce5-e618-7a61-8daf-07ca0f11f252"),
            UUID("019bbce5-e613-7cce-9e54-d93870e9ceb0"),
        ],
        reasoning_level_ids=[
            UUID("019bb58e-0ae0-76b9-a047-a56cab0551df"),
            UUID("019bb58e-0ae0-7674-8f88-3d599e46389c"),
            UUID("019bb58e-0ae0-75a8-88aa-df5679daaa42"),
            UUID("019bb58e-0ae0-7632-b146-b0bdb933c00d"),
            UUID("019bb58e-0ae0-75ee-a5d0-83b15b64064e"),
        ],
        temperature_level_ids=[
            UUID("019c441a-0e9f-700c-a8c5-11434dc2ea95"),
        ],
    ),
    dict(
        id=GPT_AUDIO_MINI,
        name="gpt-audio-mini",
        description="A cost-efficient version of GPT Audio. Accepts audio inputs and outputs, can be used in Chat Completions REST API. 128k context, 16k max output.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e608-7d5a-b937-0a22697e3f8b"),
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75ed-b882-53a18d4f5db6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e619-7bc7-a119-f4cda19853c4"),
            UUID("019bbce5-e615-7519-a48e-119f06ab35b9"),
            UUID("019bbce5-e618-7315-91c0-40ae2e80e797"),
            UUID("019bbce5-e613-763f-8532-d1640980f1cd"),
        ],
        reasoning_level_ids=[
            UUID("019bb58e-0ae0-7b0b-8f3c-0015fe2fd023"),
            UUID("019bb58e-0ae0-7a8a-8ad5-369e4f0a3c88"),
            UUID("019bb58e-0ae0-7b48-b743-747b65796171"),
            UUID("019bb58e-0ae0-7aca-ab93-c29199c5cc74"),
            UUID("019bb58e-0ae0-7b8d-9d22-0cc3f97176dd"),
        ],
        # 101 temperature levels — see _TEMP_LEVELS_FULL below
        temperature_level_ids=_TEMP_LEVELS_FULL,
    ),
    dict(
        id=GPT_AUDIO,
        name="gpt-audio",
        description="GPT Audio is OpenAI's first generally available audio model. Accepts audio inputs and outputs, can be used in Chat Completions REST API. 128k context, 16k max output.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e608-7d5a-b937-0a22697e3f8b"),
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75ed-b882-53a18d4f5db6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e619-7e21-a84f-30517116ece5"),
            UUID("019bbce5-e615-7776-ab67-d9e6d74d4241"),
            UUID("019bbce5-e618-7a61-8daf-07ca0f11f252"),
            UUID("019bbce5-e614-7dba-bfc7-104348e5a45e"),
        ],
        reasoning_level_ids=[
            UUID("019bb58e-0ae0-797c-8d92-4e2d037a302e"),
            UUID("019bb58e-0ae0-793b-a87f-4f96b77e4379"),
            UUID("019bb58e-0ae0-7a4d-87a4-b3b2af435887"),
            UUID("019bb58e-0ae0-79b8-ab5b-33c15d1eaabd"),
            UUID("019bb58e-0ae0-79fa-b9f4-fa53ec907051"),
        ],
        # 101 temperature levels — see _TEMP_LEVELS_FULL below
        temperature_level_ids=_TEMP_LEVELS_FULL,
    ),
    dict(
        id=GPT_IMAGE_1_MINI,
        name="gpt-image-1-mini",
        description="GPT Image 1 Mini (Medium Quality) - 1024x1024 resolution. OpenAI's compact image generation model with balanced quality and cost.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
        ],
        pricing_ids=[
            UUID("019bbce5-e615-7ef9-b521-fa267051866b"),
            UUID("019bbce5-e615-7c81-abb4-910688286758"),
            UUID("019bbce5-e616-73d7-bc0b-e58e7c5530ed"),
        ],
    ),
    dict(
        id=GPT_IMAGE_1,
        name="gpt-image-1",
        description="GPT Image 1 (High Quality) - 1024x1024 resolution. OpenAI's image generation model optimized for highest quality output.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e609-750d-90c6-cb39f1266e18"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
        ],
        pricing_ids=[
            UUID("019bbce5-e617-748c-abcb-8642f1d3f0c0"),
            UUID("019bbce5-e616-7b20-8526-c014d3ef1b3d"),
            UUID("019bbce5-e615-7ef9-b521-fa267051866b"),
        ],
    ),
    dict(
        id=GPT_OSS_20B,
        name="gpt-oss-20b",
        description="Open Source Running Locally",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e615-79ef-973a-92765896a8d4"),
            UUID("019bbce5-e61a-7c53-b3be-99c73691f7ff"),
            UUID("019bbce5-e60f-7cbb-8f27-ae33b2c11ccc"),
        ],
    ),
    dict(
        id=GPT_REALTIME_MINI,
        name="gpt-realtime-mini",
        description="A cost-efficient version of GPT Realtime - capable of responding to audio and text inputs in realtime over WebRTC, WebSocket, or SIP connections. 32k context, 4k max output.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e608-7d5a-b937-0a22697e3f8b"),
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75ed-b882-53a18d4f5db6"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e61b-7c35-923b-d0d99ab8e122"),
            UUID("019bbce5-e613-7a41-b4aa-e9c0612506bf"),
            UUID("019bbce5-e619-7bc7-a119-f4cda19853c4"),
            UUID("019bbce5-e61c-709b-b4d9-979bb314e5d8"),
            UUID("019bbce5-e615-7519-a48e-119f06ab35b9"),
            UUID("019bbce5-e618-7315-91c0-40ae2e80e797"),
            UUID("019bbce5-e61b-7a16-a323-95cd2a0d255f"),
            UUID("019bbce5-e613-763f-8532-d1640980f1cd"),
        ],
        # 61 temperature levels — see _TEMP_LEVELS_FULL below
        temperature_level_ids=_TEMP_LEVELS_FULL,
    ),
    dict(
        id=GPT_REALTIME,
        name="gpt-realtime",
        description="GPT Realtime is OpenAI's real-time audio model for conversational AI.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e608-7d5a-b937-0a22697e3f8b"),
            UUID("019bbce5-e606-77f1-abf8-78df7462af03"),
            UUID("019bbce5-e609-7efe-8549-87dd267f086a"),
            UUID("019c47d6-6c45-75ed-b882-53a18d4f5db6"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
            UUID("019c47d6-6c45-7602-a2b1-b2a608b0cf31"),
        ],
        pricing_ids=[
            UUID("019bbce5-e61c-76e9-afb3-e8a0812cf774"),
            UUID("019bbce5-e615-72b2-855e-ce571d75c284"),
            UUID("019bbce5-e619-7e21-a84f-30517116ece5"),
            UUID("019bbce5-e61c-74ca-b5b1-6548c9cf692b"),
            UUID("019bbce5-e615-7776-ab67-d9e6d74d4241"),
            UUID("019bbce5-e619-76f0-a364-4ceedf4f6bf7"),
            UUID("019bbce5-e61c-72ba-80a6-0f8c95e0db6c"),
            UUID("019bbce5-e615-7039-9e54-d02b6e278e6e"),
        ],
        # 61 temperature levels — see _TEMP_LEVELS_FULL below
        temperature_level_ids=_TEMP_LEVELS_FULL,
    ),
    dict(
        id=SORA_2_PRO,
        name="sora-2-pro",
        description="Sora 2 Pro (Low Quality) - 720x1280/1280x720 resolution. OpenAI's advanced video generation model optimized for cost efficiency.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e608-7d5a-b937-0a22697e3f8b"),
            UUID("019bbce5-e607-7bc4-a6b0-a4218bc8e5f8"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
        ],
        pricing_ids=[
            UUID("019bbce5-e617-770f-a354-a94fbf7fe764"),
            UUID("019bbce5-e617-7e3b-ba13-e97571ba8013"),
        ],
    ),
    dict(
        id=SORA_2,
        name="sora-2",
        description="Sora 2 is OpenAI's advanced video generation model.",
        provider_ids=[_PROVIDER["openai"]],
        flag_ids=[
            UUID("019be334-bfc4-7ef6-b18f-7a556d94b225"),
        ],
        modality_ids=[
            UUID("019bbce5-e608-7d5a-b937-0a22697e3f8b"),
            UUID("019bbce5-e607-7bc4-a6b0-a4218bc8e5f8"),
            UUID("019c47d6-6c45-75f5-abd6-9cfc54b978a6"),
            UUID("019c47d6-6c45-754d-9669-73c9882d1a66"),
        ],
        pricing_ids=[
            UUID("019bbce5-e616-7fce-ae21-4356ff8eafaf"),
        ],
    ),
]
