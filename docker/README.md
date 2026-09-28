# CAMROD Docker 참고 자료

이 폴더의 Docker 정의는 과거 배포 실험을 보존한 자료다. **v2.2.8 전체 이미지 빌드와 실행은 검증되지 않았다.** 현재 소스의 기본 빌드 방법은 저장소 루트의 [colcon_build.sh](../colcon_build.sh)와 [프로젝트 README](../README.md)를 따른다.

## 실제 파일 구성

| 파일 | 역할과 현재 상태 |
| --- | --- |
| [Dockerfile.camrod](Dockerfile.camrod) | ROS Humble 다단계 이미지 초안. 현재 전체 패키지와 React production bundle 생성 흐름을 포함하는지 보완이 필요하다. |
| [entrypoint.camrod.sh](entrypoint.camrod.sh) | ROS/workspace 환경을 읽고 전달받은 명령을 실행한다. |
| [buildx_camrod.sh](buildx_camrod.sh) | Buildx 빌드·게시 보조 스크립트. 기본값 `PUSH_IMAGE=1`이며, ARM64를 포함하면 기본적으로 privileged binfmt 설치를 수행한다. |
| [Dockerfile.base](Dockerfile.base), [Dockerfile.module](Dockerfile.module) | 보존된 모듈별 이미지 실험. 현재 패키지 의존성과 실제 컨테이너 실행 재검증이 필요하다. |
| [build_module.sh](build_module.sh), [run_module.sh](run_module.sh) | 스크립트가 있는 소스 경로와 명령 인자를 보존하도록 수정했다. 기본 이미지는 `camrod/base:humble`로 통일하며 `BASE_IMAGE`로 바꿀 수 있다. Docker stub을 이용한 경로·인자 검사만 실행했다. |
| [compose.modules.yaml](compose.modules.yaml) | 보존된 모듈별 compose 구성. 현재 전체 로봇 실행 경로로 검증되지 않았다. |

## 경로와 재검증 조건

`Dockerfile.camrod`의 `COPY`와 소스 검사 단계는 빌드 context 바로 아래에
`camrod_bringup`, `camrod_common` 등의 소스가 있다고 가정한다. 이 workspace에서는
context가 `/home/nvidia/camrod_ws/src`이고 Dockerfile은 그 아래
`docker/Dockerfile.camrod`다. `buildx_camrod.sh`의 기본
`WORKSPACE_ROOT=/home/camrod_ws`를 그대로 사용하면 현재 배치와 맞지 않는다.

```bash
# 저장소 src 루트에서, Dockerfile의 현재 패키지/프런트엔드 구성을 먼저 보완한 뒤 사용한다.
# 로컬 단일 아키텍처 빌드 예시이며 이번 검증에서 실행한 명령이 아니다.
WORKSPACE_ROOT="$PWD" DOCKERFILE_REL=docker/Dockerfile.camrod \
  IMAGE_TAG=v2.2.8-local PLATFORMS=linux/arm64 \
  PUSH_IMAGE=0 INSTALL_BINFMT=0 ./docker/buildx_camrod.sh
```

호스트 아키텍처와 같은 `PLATFORMS`를 선택한다. Docker 이미지의 패키지 설치,
UI bundle, 음성/카메라 드라이버, 장치 전달과 ROS 통신을 실제로 검증하기 전에는
이 정의를 현장 배포 완료 자료로 사용하지 않는다. 2026-09-15 점검은 소스 및 셸
구문 확인 범위이며 이미지 빌드·registry 게시·컨테이너 실차 실행을 포함하지 않는다.
