import runpod
from steps.model_generator import generate_3d_model


def handler(job):
    """
    RunPod Serverless 진입점

    백엔드 입력:
    {
        "input": {
            "job_id": "uuid-xxxx",
            "image_url": "https://s3.../preprocessed.png"
        }
    }

    반환:
    {
        "glb_url": "https://s3.../model.glb"
    }
    """
    try:
        input_data = job["input"]
        job_id     = input_data["job_id"]
        image_url  = input_data["image_url"]

        print(f"[{job_id}] 작업 시작")
        result = generate_3d_model(job_id, image_url)
        return result

    except KeyError as e:
        return {"error": f"입력값 누락: {str(e)}"}
    except Exception as e:
        return {"error": f"처리 중 오류 발생: {str(e)}"}


runpod.serverless.start({"handler": handler})