class PreprocessorService:
    async def preprocess(self, image_url: str) -> str:
        # TODO: Grounding DINO + SAM으로 가구 객체 추출 (배경 제거)
        # TODO: LaMa로 배경 인페인팅
        # 반환: 전처리된 이미지 경로 또는 base64 문자열
        raise NotImplementedError
