# GPU 구성

CPU 도구와 뷰어는 GPU 학습 환경 없이 사용할 수 있습니다. 아래는 전체 재구성에만 필요합니다.

## 백엔드

Linux 또는 Windows의 WSL2에서 NVIDIA CUDA 환경을 준비하고, 별도의 백엔드를 받습니다.

```bash
git clone https://github.com/tardis7732/streetview-to-ply.git ../streetview-to-ply
git -C ../streetview-to-ply checkout 3211651201467682ebdd92e3c81504234be5c468
```

[백엔드 GPU 설치 안내](https://github.com/tardis7732/streetview-to-ply/blob/3211651201467682ebdd92e3c81504234be5c468/docs/GPU_SETUP.md)에 따라 PyCOLMAP 4.2, Brush 0.3, PyTorch, gsplat 및 필요한 모델을 설치합니다. 현재 toolkit은 이 커밋의 내부 Python API에 맞춰져 있습니다. 다른 커밋을 사용하려면 `--allow-unpinned-backend`로 명시해야 합니다.

`sfm`과 `train`은 같은 GPU Python 환경에서 실행합니다. 별도의 SSH 실행기나 비밀번호를 포함하지 않습니다. 원격 서버를 쓰는 경우 코드를 서버에 설치한 뒤 그 서버의 쉘에서 CLI를 실행하세요.

## Google 수집과 도로 분류

Python 3.12+ 환경에서 `python -m pip install -e ".[google]"`를 사용합니다. 지정된 YellowO2 패키지와 그 모델 의존성이 설치됩니다. 도로 분류는 Cityscapes 계열 라벨의 도로/보도(0, 1)를 사용하고, 사람·차량·하늘(10–18)을 정리 보호 대상으로 취급합니다.

## 학습 설정

- 고정 큐브 6면, 면당 1280px, focal=640.
- 실제 시각 대응점 기반 SfM. GPS는 메트릭 정렬 보조값입니다.
- 전부 학습용으로 사용하며 별도 정답 시점 품질 평가를 주장하지 않습니다.
- Brush: 40,000단계, SH degree 2, 기본 최대 4,000,000 Gaussian.
- gsplat: fixed population 6,000단계, opacity regularization 0.03, scale regularization 0.05, 실제 SfM track inverse-depth weight 0.002.
- 학습 RGB는 전부 유효 마스크입니다. 사람·차량·하늘 제거용 마스크를 적용하지 않습니다.

Brush는 `--brush /absolute/path/to/brush_app`로 지정합니다. gsplat의 실제 로드된 CUDA 렌더러 파일 SHA256을 계산해 추가 학습 명령에 넣습니다. 빌드 캐시 위치를 지정하려면 운영 환경에서 `TORCH_EXTENSIONS_DIR`를 설정하세요.

GPU 작업에는 충분한 디스크와 VRAM이 필요하며, 촬영 지점 수·해상도·Gaussian 수에 따라 달라집니다. 공개 코드의 CPU 검증 결과를 GPU 설치 완료나 전체 학습 성공으로 해석하면 안 됩니다.
