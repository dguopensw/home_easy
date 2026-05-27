# IKEA Dimension Prior Builder

IKEA-Dataset zip 파일에서 제품 치수 텍스트와 이미지 경로를 정리해 GPT Vision 치수 추정값 검증용 prior CSV를 생성하는 스크립트입니다.

기존 백엔드 서비스 코드, 프론트, API 라우터, SAM3, `dimension_estimator.py`는 수정하지 않습니다. 이 폴더는 데이터셋 정리 실험용입니다.

## 실행 방법

프로젝트 루트에서 실행합니다.

```bash
python experiments/ikea_dimension_prior/build_ikea_priors.py \
  --dataset-root /Users/dahoo/home_easy/datasets/IKEA-Dataset \
  --output-dir experiments/ikea_dimension_prior/data
```

## 입력 데이터

스크립트는 `--dataset-root` 아래의 `*.zip` 파일을 자동으로 찾습니다.

`extracted/{zip_name}/` 폴더가 없으면 자동으로 압축을 해제합니다.

예:

```text
datasets/IKEA-Dataset/
  Bedroom.zip
  HomeOffice.zip
  Living Room 1.zip
  extracted/
    Bedroom/
    HomeOffice/
    Living Room 1/
```

치수 텍스트는 두 가지 형태를 처리합니다.

```text
Dimension Counter_00327772 Width: 145cm Length: 92cm Height: 180cm Material: Wood
```

```text
19028754
Width: 96 cm Depth: 37 cm Height: 214 cm Max. load/shelf: 35 kg
```

## 출력 파일

```text
experiments/ikea_dimension_prior/data/ikea_dimensions_clean.csv
experiments/ikea_dimension_prior/data/ikea_dimension_priors.csv
experiments/ikea_dimension_prior/data/ikea_dimension_outliers.csv
```

### ikea_dimensions_clean.csv

제품 실제 치수로 판단되고, width/depth/height가 모두 있으며, 값이 정상 범위인 row만 들어갑니다.

컬럼:

```text
room_category
normalized_category
raw_category
product_name
product_id
width_cm
depth_cm
height_cm
material
image_path
raw_dimension_text
```

### ikea_dimension_outliers.csv

clean prior에서 제외된 row입니다.

주요 제외 사유:

- `missing_dimension`: width/depth/height 중 하나 이상 없음
- `dimension_out_of_range`: 5cm 미만 또는 500cm 초과
- `package_dimension`: 포장 치수 문맥
- `missing_product_id`: 상품 ID를 찾지 못함

`Package Number`, `Package`, `packaging`, `package measurement`, `package(s)` 문맥의 치수는 제품 실제 치수가 아니라 포장 치수로 보고 clean prior에서 제외합니다.

### ikea_dimension_priors.csv

`normalized_category`와 축별 통계입니다.

컬럼:

```text
category
axis
count
mean
median
p05
p10
p25
p75
p90
p95
min
max
is_unreliable
```

`axis` 값은 아래 세 개입니다.

```text
width_cm
depth_cm
height_cm
```

`count < 20`인 prior row는 `is_unreliable=true`로 표시합니다. 이 카테고리는 표본 수가 작아서 검증 기준으로 사용할 때 주의해야 합니다.

## 단위 변환

모든 치수는 cm로 저장합니다.

- `cm`: 그대로 사용
- `mm`: `/ 10`
- `m`: `* 100`
- `inch`, `in`: `* 2.54`

`Length`는 `depth_cm`으로 매핑합니다. 단, 카테고리에 따라 실제 의미가 depth 또는 length일 수 있으며, 본 prior는 정확한 축 보정이 아니라 극단값 필터링용입니다.

## 카테고리 정규화

`normalized_category`는 product_name보다 폴더 경로의 category명을 우선 사용합니다. 폴더명으로 판단이 어려울 때 product_name을 보조로 사용합니다.

현재 매핑 예:

- `Counter` -> `cabinet`
- `Cabinet` -> `cabinet`
- `Coat_Stand` -> `rack`
- `Desk` -> `desk`
- `Table` -> `table`
- `Chair` -> `chair`
- `Sofa` -> `sofa`
- `Bed` -> `bed`
- `Bookcase`, `Bookshelf` -> `bookshelf`
- `Dresser`, `Chest`, `Drawer`, `Chest of drawers` -> `dresser`
- `Wardrobe` -> `wardrobe`
- `Shelf`, `Shelving`, `Shelving unit` -> `shelf`
- `TV bench`, `TV unit`, `TV stand`, `Media unit` -> `tv_unit`
- `Sideboard` -> `sideboard`
- `Drawer unit` -> `drawer_unit`
- `Storage combination` -> `storage`

## 실행 후 확인할 것

스크립트 실행이 끝나면 아래 요약이 출력됩니다.

```text
Total parsed products: ...
Clean rows: ...
Outlier rows: ...
Category counts:
  bookshelf: ...
  cabinet: ...
Generated files:
  ...
```

확인 포인트:

- `ikea_dimensions_clean.csv`에 포장 치수가 섞이지 않았는지 확인
- `image_path`가 product id 이미지와 연결되는지 확인
- `ikea_dimension_priors.csv`에서 `count < 20`인 row는 `is_unreliable=true`인지 확인
- `Length`가 들어간 row는 `depth_cm`으로 들어갔는지 확인
