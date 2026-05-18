import threading
from flask import Flask, request, jsonify
from steps.model_generator import generate_3d_model

app = Flask(__name__)

# 작업 상태 저장소
jobs = {}


def run_job(job_id, image_url):
    """백그라운드에서 3D 생성 실행"""
    try:
        jobs[job_id] = {"status": "processing"}
        result = generate_3d_model(job_id, image_url)
        jobs[job_id] = {"status": "completed", "glb_url": result["glb_url"]}
    except Exception as e:
        jobs[job_id] = {"status": "failed", "error": str(e)}


@app.route("/generate", methods=["POST"])
def generate():
    """
    요청 받으면 바로 accepted 반환하고 백그라운드에서 생성 시작

    요청:
    { "job_id": "uuid-xxxx", "image_url": "https://s3.../image.png" }

    응답:
    { "status": "accepted", "job_id": "uuid-xxxx" }
    """
    try:
        data      = request.json
        job_id    = data["job_id"]
        image_url = data["image_url"]

        # 백그라운드 스레드로 실행
        thread = threading.Thread(target=run_job, args=(job_id, image_url))
        thread.daemon = True
        thread.start()

        return jsonify({"status": "accepted", "job_id": job_id}), 202

    except KeyError as e:
        return jsonify({"error": f"입력값 누락: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"처리 중 오류: {str(e)}"}), 500


@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    """
    백엔드가 2초마다 폴링하는 상태 확인 엔드포인트

    응답 예시:
    { "status": "processing" }
    { "status": "completed", "glb_url": "https://s3.../model.glb" }
    { "status": "failed", "error": "..." }
    { "status": "not_found" }
    """
    if job_id not in jobs:
        return jsonify({"status": "not_found"}), 404

    return jsonify(jobs[job_id]), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)