import os
import time
import requests
import boto3
import torch
from PIL import Image
from io import BytesIO
from trellis2.pipelines import Trellis2ImageTo3DPipeline
import o_voxel

AWS_BUCKET            = os.environ.get("AWS_BUCKET")
AWS_REGION            = os.environ.get("AWS_REGION", "ap-northeast-2")
AWS_ACCESS_KEY_ID     = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

# ========================================
# 모델 전역 로딩 (컨테이너 시작 시 1회만)
# ========================================
print("🚀 TRELLIS.2 모델 로딩 중...")
pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
pipeline.cuda()
print("✅ 모델 로딩 완료!")


def download_image(image_url: str) -> Image.Image:
    """백엔드가 보낸 이미지 URL에서 PIL Image로 변환"""
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    return Image.open(BytesIO(response.content)).convert("RGBA")


def upload_to_s3(local_path: str, job_id: str) -> str:
    """생성된 GLB 파일을 S3에 업로드하고 URL 반환"""
    s3 = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    s3_key = f"models/{job_id}.glb"
    s3.upload_file(
        local_path,
        AWS_BUCKET,
        s3_key,
        ExtraArgs={"ContentType": "model/gltf-binary"}
    )
    glb_url = f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
    return glb_url


def generate_3d_model(job_id: str, image_url: str) -> dict:
    """
    백엔드에서 받은 이미지로 3D 모델 생성 후 S3 업로드

    Returns:
        { "glb_url": "https://s3.../model.glb" }
    """
    # 1. 이미지 다운로드
    print(f"[{job_id}] 이미지 다운로드 중...")
    image = download_image(image_url)

    # 2. TRELLIS.2로 3D 생성
    print(f"[{job_id}] 3D 모델 생성 중... (약 120초 소요)")
    start_t = time.time()
    mesh = pipeline.run(
        image,
        seed=42,
        # 전체적인 윤곽을 잡 단계
        sparse_structure_sampler_params={
            "steps": 20,
            "guidance_strength": 7.5,
            "guidance_rescale": 0.7,
            "rescale_t": 5.0,
        },
        # 만들어진 뼈대 위에 살 붙이는 단계
        shape_slat_sampler_params={
            "steps": 20,
            "guidance_strength": 7.5,
            "guidance_rescale": 0.5,
            "rescale_t": 3.0,
        },
        # 색칠하는 단계
        tex_slat_sampler_params={
            "steps": 20,
            "guidance_strength": 3.0,
            "guidance_rescale": 0.0,
            "rescale_t": 3.0,
        }
    )[0]
    print(f"[{job_id}] 3D 생성 완료! ({time.time() - start_t:.1f}초)")

    # 3. GLB 변환 파라미터값 조정
    print(f"[{job_id}] GLB 변환 중...")
    glb = o_voxel.postprocess.to_glb(
        vertices          = mesh.vertices,
        faces             = mesh.faces,
        attr_volume       = mesh.attrs,
        coords            = mesh.coords,
        attr_layout       = mesh.layout,
        voxel_size        = mesh.voxel_size,
        aabb              = [[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target = 100000,
        texture_size      = 4096,
        remesh            = True,
        remesh_band       = 1,
        remesh_project    = 0,
        verbose           = False,
    )

    # 4. 임시 저장
    local_path = f"/tmp/{job_id}.glb"
    glb.export(local_path, extension_webp=False)
    print(f"[{job_id}] GLB 저장 완료: {local_path}")

    # 5. S3 업로드
    print(f"[{job_id}] S3 업로드 중...")
    glb_url = upload_to_s3(local_path, job_id)
    print(f"[{job_id}] 업로드 완료: {glb_url}")

    # 6. GPU 메모리 정리
    torch.cuda.empty_cache()

    return {"glb_url": glb_url}