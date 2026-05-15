class DimensionEstimatorService:
    async def estimate(self, image_path: str) -> dict:
        # TODO: Metric3D로 단일 이미지에서 가구 치수 추정
        # 반환: {"w": float, "h": float, "d": float}  # 단위: cm
        raise NotImplementedError
