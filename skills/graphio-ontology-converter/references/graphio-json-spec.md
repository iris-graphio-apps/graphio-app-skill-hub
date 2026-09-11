# graphio JSON 규격 요약

사내 문서 `docs/ExportImport.md`(교환 규격)와 `docs/OntologyConcept.md`(개념)에서 **파일을 만들 때 필요한 것만** 뽑았다. 원문과 어긋나면 원문이 맞다.

## 목차

1. [최상위 구조](#1-최상위-구조)
2. [objectTypes](#2-objecttypes)
3. [linkTypes](#3-linktypes)
4. [metaTypes](#4-metatypes)
5. [objectMapping](#5-objectmapping)
6. [데이터 타입 7종](#6-데이터-타입-7종)
7. [파일에 넣지 않는 값](#7-파일에-넣지-않는-값)
8. [JSON Schema](#8-json-schema)
9. [스키마가 잡지 못하는 교차 규칙](#9-스키마가-잡지-못하는-교차-규칙)
10. [GOS 코드표](#10-gos-코드표)
11. [전체 예시](#11-전체-예시)
12. [운영 반출물에 실제로 나타나는 형태](#12-운영-반출물에-실제로-나타나는-형태)

---

## 1. 최상위 구조

```jsonc
{
  "objectTypes":   [ /* 업무 개념 */ ],
  "linkTypes":     [ /* 개념 사이 관계 */ ],
  "metaTypes":     [ /* 대상 환경 데이터 구조를 가리키는 참조 */ ],
  "objectMapping": [ /* 개념 ↔ 데이터 연결 */ ]
}
```

| 규칙 | 내용 |
|---|---|
| 허용 키 | 위 네 개만. 다른 키가 있으면 반입이 `GOS50001` 로 거부된다 |
| 필수 | `objectTypes`·`linkTypes` 는 배열이어야 한다. `metaTypes`·`objectMapping` 은 생략해도 되지만 빈 배열로 남겨 두는 편이 낫다 |
| 빈 파일 | `objectTypes` 와 `linkTypes` 가 모두 0건이면 반입은 되지만 적용이 `GOS61203` 으로 거부된다 |
| 인코딩 | UTF-8 |
| 크기 | 기본 상한 10MB. 넘으면 `GOS30005` |

---

## 2. objectTypes

업무에서 다루는 개념 하나가 Object Type 하나다. 구조만 정의하고 데이터는 담지 않는다.

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `name` | string | 필수 | `^[a-zA-Z가-힣][a-zA-Z0-9가-힣_]{0,49}$` · 파일 안에서 유일 |
| `description` | string, null | 선택 | 5000자 이하 (넘으면 `GOS61003`) |
| `colorCode` | string | 필수 | `#RRGGBB` · 없으면 `GOS61004` |
| `isPublic` | boolean | 선택 | 생략하면 `false` |
| `properties` | array | 필수 | 1건 이상 (0건이면 `GOS61005`) |

### objectTypes[].properties[]

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `name` | string | 필수 | Object Type 안에서 유일 (겹치면 `GOS61010`) |
| `dataType` | enum | 필수 | 7종 중 하나 (§6) |
| `orderNo` | integer | 필수 | 1 이상 · Object Type 안에서 유일 · 1부터 연속으로 붙인다 |
| `description` | string, null | 선택 | 5000자 이하 |
| `isTitleKey` | boolean | 사실상 필수 | Object Type 당 `true` 정확히 1개 (0개 `GOS61006`, 2개 이상 `GOS61007`) |
| `isPrimaryKey` | boolean | 선택 | Object Type 당 `true` 1개 이하 (2개 이상 `GOS61008`) |

반입은 `isTitleKey` 대신 `title`, `isPrimaryKey` 대신 `pk`·`isPkKey` 도 읽어 준다. 새로 만드는 파일에서는 **규격 키만 쓴다** — 별칭을 쓰면 반출한 파일과 모양이 달라져 나중에 대조하기 어렵다.

### 식별 속성과 대표 표시 속성의 차이

| | `isPrimaryKey` | `isTitleKey` |
|---|---|---|
| 뜻 | 개체를 유일하게 가리키는 값 | 사람이 개체를 알아보는 대표 표시값 |
| 개수 | 0개 또는 1개 | 정확히 1개 |
| 예 | 고객 ID, 주문번호 | 고객명, 상품명 |
| 관계와의 연관 | 조인 속성으로 흔히 쓰이지만 강제는 아니다 | 없다 |

---

## 3. linkTypes

두 Object Type 사이의 관계다. **값이 같은지 보는 조인**이므로 양쪽 조인 속성이 반드시 있어야 한다.

```
Order.customer_id  ==  Customer.id
(source, sourcePropertyName)   (target, targetPropertyName)
```

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `name` | string | 필수 | 이름 중복이 허용된다 (양끝이 다르면 별개 관계) · 없으면 `GOS61102` |
| `description` | string, null | 선택 | 5000자 이하 |
| `sourceObjectTypeName` | string | 필수 | `objectTypes[].name` 중 하나 · 없으면 `GOS61107` |
| `sourcePropertyName` | string | 필수 | source Object Type 의 속성 이름 (`GOS61108` 없음 / `GOS61109` 미존재) |
| `targetObjectTypeName` | string | 필수 | source 와 달라야 한다 (같으면 `GOS61106`) |
| `targetPropertyName` | string | 필수 | target Object Type 의 속성 이름 (`GOS61110` / `GOS61111`) |
| `direct` | enum | 필수 | 아래 3종 · 없으면 `GOS61103` |

### direct 3종

| 값 | 뜻 | 읽는 법 |
|---|---|---|
| `UNIDIRECTIONAL` | source → target | "주문이 고객을 가리킨다" |
| `REVERSE_DIRECTIONAL` | target → source | "고객이 주문을 가리킨다" (정의는 주문 쪽에서 했으나 화살표는 반대) |
| `BIDIRECTIONAL` | 양방향 | "주문과 고객이 서로를 가리킨다" |

방향은 그래프 탐색과 화면 표시에 쓰는 뜻 정보다. 조인 자체는 방향과 무관하게 값이 같으면 성립한다.

관계의 양끝은 **같은 파일 안의 `objectTypes` 에서만 풀린다.** 반입 환경에 이미 있는 Object Type 이름을 가리켜도 풀리지 않고 `GOS61107` 이 붙는다. 관계를 옮기려면 양끝 Object Type 도 같은 파일에 담는다.

---

## 4. metaTypes

**대상 환경에 이미 있는 데이터 구조를 이름으로 가리키는 참조다.** 반입이 Meta Type 을 만들어 주지 않는다 — 이름을 찾지 못하면 `GOS61014` 로 표시되고 새로 생기지 않는다.

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `name` | string | 필수 | 파일 안에서 유일 (겹치면 `GOS61018`) · 대상 환경의 게시된 Meta Type 이름과 정확히 같아야 풀린다 |
| `description` | string, null | 선택 | 길이 제한 없음 · 참고용이며 대상 환경의 값을 바꾸지 않는다 |
| `metaTypeKind` | enum | 선택 | `CUSTOM` `PARSING` `DOC_TYPE` |
| `properties` | array | 선택 | 아래 |

### metaTypes[].properties[]

| 필드 | 타입 | 설명 |
|---|---|---|
| `name` | string | Graphio 가 쓰는 컬럼 이름. `propertyMappings[].metaTypePropertyName` 이 이 값을 가리킨다 |
| `dataType` | enum | 7종 (§6) |
| `rawDataPropertyName` | string, null | 원천 컬럼명 (예: `CUST_NM`) · 참고 정보 |
| `description` | string, null | 1000자 이하 |

이 블록은 **네 필드로 고정**된다. 연결 정보·스키마명·테이블명·워크플로·청킹 설정처럼 환경마다 다른 값은 반출·반입 어느 쪽에도 들어가지 않는다.

### metaTypeKind 3종

| 값 | 뜻 |
|---|---|
| `CUSTOM` | 정형 데이터(테이블·CSV) 기반, 또는 사람이 직접 정의한 것 |
| `PARSING` | 비정형 문서를 파싱해 청크·임베딩 단위로 적재한 것 |
| `DOC_TYPE` | 문서 타입의 탐색·출력 속성에서 파생된 것 |

문서에 근거가 없으면 `CUSTOM` 으로 둔다. 테이블·CSV 기반이 대부분이다.

---

## 5. objectMapping

"이 개념의 데이터는 이 데이터 구조에서 온다"를 정한다. Object Type 1건과 Meta Type 1건의 쌍이 항목 1건이다.

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `objectTypeName` | string | 필수 | `objectTypes[].name` 중 하나 (없으면 `GOS61021`) |
| `metaTypeName` | string | 필수 | `metaTypes[].name` 중 하나이자 대상 환경에 있어야 한다 |
| `propertyMappings` | array | 필수 | 1건 이상 (0건이면 `GOS61016` 이 붙어 적용이 막힌다) |

### objectMapping[].propertyMappings[]

| 필드 | 제약 |
|---|---|
| `objectTypePropertyName` | 해당 Object Type 의 속성 이름 (`GOS61022`) · 한 objectMapping 안에서 유일 (`GOS61020`) |
| `metaTypePropertyName` | 해당 Meta Type 의 컬럼 이름 (`GOS61015`) |

`(objectTypeName, metaTypeName)` 쌍만 유일하면 되므로 다음이 모두 정상이다.

- 한 Object Type 이 여러 Meta Type 에 매핑된다 (고객 ← CRM 고객마스터 + 멤버십 회원테이블)
- 한 Meta Type 이 여러 Object Type 에서 참조된다 (주문상세 테이블 → 주문, 주문품목)
- 여러 Object Type 속성이 같은 컬럼을 가리킨다

한 objectMapping 안에서 Object Type 속성 하나는 컬럼 하나에만 연결된다. 그 반대는 막지 않는다.

---

## 6. 데이터 타입 7종

원천 DB 의 여러 컬럼 타입을 7종으로 표준화한다.

| 값 | 뜻 | 원천 타입 예 |
|---|---|---|
| `INTEGER` | 정수 | int, int2, int4, int8, bigint, smallint |
| `TEXT` | 문자열 | text, varchar, char, uuid |
| `DATETIME` | 날짜·시간 | date, timestamp, time, interval |
| `FLOAT8` | 실수 | float, double precision, numeric, decimal, real |
| `BOOLEAN` | 참/거짓 | bool, boolean, bit |
| `VECTOR` | 임베딩 벡터 | vector, halfvec, sparsevec |
| `UNKNOWN` | 판별 불가 | 대응되지 않는 타입 |

판별 규칙: 타입 이름에 `time`·`date` 가 들어가면 `DATETIME`, 위 표에 없으면 `TEXT` 로 본다. `UNKNOWN` 은 실제로 판별할 수 없을 때만 쓴다 — 문서를 덜 읽어서 쓰는 값이 아니다.

위 판별 규칙은 **Graphio 가 원천 DB 타입을 7종으로 표준화하는 방식**이다. 이 스킬이 타입을 정하는 규칙이 아니다.

**데이터 타입은 문서가 적는다.** 서식의 `데이터 타입` 칸에 7종 중 하나를 적고, 파서는 7종에 없는 값을 바꾸지 않고 몇 줄인지 알린다. 속성 이름으로 타입을 짐작하지 않는다 — `..._yn` 이 `BOOLEAN` 일지 `TEXT` 일지는 문서가 말할 일이다.

---

## 7. 파일에 넣지 않는 값

환경이 채우거나 환경마다 다른 값이다. 파일에 적어도 반입 과정에서 지워진다.

| 대상 | 넣지 않는 키 |
|---|---|
| Object Type | `id` `owner` `ownerId` `objectTypeGroupIds` `projectIds` `status` `metaTypeIds` `metaTypeProperties` |
| Link Type | `id` `ownerId` `sourceObjectTypeId` `targetObjectTypeId` `projectIds` `status` |
| Meta Type | 연결 정보·스키마명·테이블명·워크플로·임베딩 모델·청킹 설정·`draft`·`softDeleted` 등 §4 표에 없는 모든 키 |
| 공통 | `__` 로 시작하는 내부 마커 키 |

Link Type 의 `status` 는 "양끝 Object Type 이 모두 풀렸는가"로 반입 때 다시 계산된다. Object Type Group 과 프로젝트 소속도 환경마다 달라 교환 대상에서 빠진다.

---

## 8. JSON Schema

형식만 기계로 점검하는 용도다. 이름 유일성과 교차 참조는 표현할 수 없어 §9 로 보완한다. 이 스킬의 검증기는 두 가지를 함께 본다.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Graphio Ontology Exchange (graphio JSON)",
  "type": "object",
  "additionalProperties": false,
  "required": ["objectTypes", "linkTypes"],
  "properties": {
    "objectTypes":   { "type": "array", "items": { "$ref": "#/$defs/objectType" } },
    "linkTypes":     { "type": "array", "items": { "$ref": "#/$defs/linkType" } },
    "metaTypes":     { "type": "array", "items": { "$ref": "#/$defs/metaType" } },
    "objectMapping": { "type": "array", "items": { "$ref": "#/$defs/objectMapping" } }
  },
  "$defs": {
    "dataType": { "enum": ["INTEGER", "TEXT", "DATETIME", "FLOAT8", "BOOLEAN", "VECTOR", "UNKNOWN"] },
    "objectType": {
      "type": "object",
      "required": ["name", "colorCode", "properties"],
      "properties": {
        "name": { "type": "string", "pattern": "^[a-zA-Z가-힣][a-zA-Z0-9가-힣_]{0,49}$" },
        "description": { "type": ["string", "null"], "maxLength": 5000 },
        "colorCode": { "type": "string", "minLength": 1 },
        "isPublic": { "type": "boolean" },
        "properties": { "type": "array", "minItems": 1, "items": { "$ref": "#/$defs/objectTypeProperty" } }
      }
    },
    "objectTypeProperty": {
      "type": "object",
      "required": ["name", "dataType", "orderNo"],
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "dataType": { "$ref": "#/$defs/dataType" },
        "orderNo": { "type": "integer", "minimum": 1 },
        "description": { "type": ["string", "null"], "maxLength": 5000 },
        "isTitleKey": { "type": "boolean" },
        "isPrimaryKey": { "type": "boolean" }
      }
    },
    "linkType": {
      "type": "object",
      "required": ["name", "sourceObjectTypeName", "sourcePropertyName", "targetObjectTypeName", "targetPropertyName", "direct"],
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "description": { "type": ["string", "null"], "maxLength": 5000 },
        "sourceObjectTypeName": { "type": ["string", "null"] },
        "sourcePropertyName": { "type": "string", "minLength": 1 },
        "targetObjectTypeName": { "type": ["string", "null"] },
        "targetPropertyName": { "type": "string", "minLength": 1 },
        "direct": { "enum": ["UNIDIRECTIONAL", "REVERSE_DIRECTIONAL", "BIDIRECTIONAL"] }
      }
    },
    "metaType": {
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "description": { "type": ["string", "null"] },
        "metaTypeKind": { "enum": ["CUSTOM", "PARSING", "DOC_TYPE"] },
        "properties": { "type": "array", "items": { "$ref": "#/$defs/metaTypeProperty" } }
      }
    },
    "metaTypeProperty": {
      "type": "object",
      "required": ["name", "dataType"],
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "dataType": { "$ref": "#/$defs/dataType" },
        "rawDataPropertyName": { "type": ["string", "null"] },
        "description": { "type": ["string", "null"] }
      }
    },
    "objectMapping": {
      "type": "object",
      "required": ["objectTypeName", "metaTypeName", "propertyMappings"],
      "properties": {
        "objectTypeName": { "type": "string", "minLength": 1 },
        "metaTypeName": { "type": "string", "minLength": 1 },
        "propertyMappings": { "type": "array", "items": { "$ref": "#/$defs/propertyMapping" } }
      }
    },
    "propertyMapping": {
      "type": "object",
      "required": ["objectTypePropertyName", "metaTypePropertyName"],
      "properties": {
        "objectTypePropertyName": { "type": "string", "minLength": 1 },
        "metaTypePropertyName": { "type": "string", "minLength": 1 }
      }
    }
  }
}
```

스키마는 **운영 반출물이 통과하도록** 정해졌다. 그래서 `propertyMappings` 의 빈 배열과 양끝이 `null` 인 관계를 형식으로는 허용하고, 그것들은 반입 검증(`GOS61016`·`GOS61107`)이 잡는다. 새로 만드는 파일에서는 둘 다 쓰지 않는다.

---

## 9. 스키마가 잡지 못하는 교차 규칙

| # | 규칙 | 위반 시 |
|---|---|---|
| 1 | `objectTypes[].name` 이 파일 안에서 유일 | `GOS61011` |
| 2 | 한 Object Type 안에서 속성 이름이 유일 | `GOS61010` |
| 3 | 한 Object Type 안에서 `isTitleKey: true` 가 정확히 1개 | `GOS61006` / `GOS61007` |
| 4 | 한 Object Type 안에서 `isPrimaryKey: true` 가 1개 이하 | `GOS61008` |
| 5 | 관계의 양끝 이름이 `objectTypes[].name` 에 있다 | `GOS61107` |
| 6 | source 와 target 이 다르다 | `GOS61106` |
| 7 | 조인 속성 이름이 각 Object Type 의 속성에 있다 | `GOS61109` / `GOS61111` |
| 8 | `metaTypes[].name` 이 파일 안에서 유일 | `GOS61018` |
| 9 | `(objectTypeName, metaTypeName)` 쌍이 유일 | `GOS61019` |
| 10 | 한 objectMapping 안에서 `objectTypePropertyName` 이 유일 | `GOS61020` |
| 11 | `objectTypePropertyName` 이 해당 Object Type 에 있다 | `GOS61022` |
| 12 | `metaTypeName` 이 대상 환경에 게시된 Meta Type 으로 있다 | `GOS61014` (없음) / `GOS61023` (동명 2건 이상) |
| 13 | `metaTypePropertyName` 이 해당 Meta Type 에 있다 | `GOS61015` |
| 14 | 모든 Object Type 에 objectMapping 이 1건 이상 | `GOS61017` |
| 15 | 각 objectMapping 의 `propertyMappings` 가 1건 이상 | `GOS61016` |
| 16 | Object Type `description` 이 5000자 이하 | `GOS61003` |
| 17 | 이름이 같고 양끝이 다른 관계 | 경고 `GOS61330` (허용) |

12·13·14 는 대상 환경을 봐야 확정된다. 그래서 이 스킬의 검증기는 셋을 "보류"로 보고한다.

---

## 10. GOS 코드표

### 요청 자체가 실패하는 코드

| 코드 | 상황 |
|---|---|
| `GOS20006` | 임시저장본이 있는 상태에서 반입 시도 |
| `GOS30005` | 파일명·확장자 없음, 크기 상한 초과 |
| `GOS30006` | 허용하지 않는 확장자 |
| `GOS20009` | JSON 파싱 실패 |
| `GOS50001` | 최상위 키 위반 |
| `GOS61202` | 검증 오류가 있어 적용 불가 |
| `GOS61203` | `objectTypes`·`linkTypes` 가 모두 0건이어서 적용 불가 |

### 검증 오류 (적용이 막힌다)

| 코드 | 대상 | 뜻 |
|---|---|---|
| `GOS61002` | Object Type | 이름 형식 위반 |
| `GOS61003` | Object Type | 설명 5000자 초과 |
| `GOS61004` | Object Type | `colorCode` 없음 |
| `GOS61005` | Object Type | 속성 0건 |
| `GOS61006` / `GOS61007` | Object Type | 대표 표시 속성 0개 / 2개 이상 |
| `GOS61008` | Object Type | 식별 속성 2개 이상 |
| `GOS61010` | 속성 | 속성 이름 중복 |
| `GOS61011` | Object Type | Object Type 이름 중복 |
| `GOS61014` | Meta Type | 대상 환경에서 Meta Type 이름을 찾지 못함 |
| `GOS61015` | Object Mapping | Meta Type 컬럼 이름을 찾지 못함 |
| `GOS61016` | Object Mapping | `propertyMappings` 0건, 또는 참조되지 않는 Meta Type |
| `GOS61017` | Object Type | Object Mapping 0건 |
| `GOS61018` | Meta Type | 파일 안 Meta Type 이름 중복 |
| `GOS61019` | Object Mapping | `(objectTypeName, metaTypeName)` 중복 |
| `GOS61020` | Property Mapping | `objectTypePropertyName` 중복 |
| `GOS61021` / `GOS61022` | Object Mapping | Object Type / 그 속성이 없음 |
| `GOS61023` | Meta Type | 동명 Meta Type 이 대상 환경에 2건 이상 |
| `GOS61102` / `GOS61103` | Link Type | 이름 없음 / `direct` 없음 |
| `GOS61105` | Link Type | 완전 중복 |
| `GOS61106` | Link Type | 자기 참조 |
| `GOS61107` | Link Type | 양끝 Object Type 없음 |
| `GOS61108` / `GOS61109` | Link Type | source 조인 속성 없음 / 미존재 |
| `GOS61110` / `GOS61111` | Link Type | target 조인 속성 없음 / 미존재 |

### 경고 (적용을 막지 않는다)

| 코드 | 뜻 |
|---|---|
| `GOS61330` | 관계 이름 충돌 (같은 이름, 양끝이 다름) |
| `GOS61335` | 반입 항목이 기존 항목과 같아 병합됨 |
| `GOS61336` | 반출 시 동명 Object Type / Meta Type 존재 |
| `GOS61337` | 요소 제거 (풀리지 않은 양끝, 불용 매핑, 참조되지 않는 Meta Type) |
| `GOS61343` | 반입 항목이 기존 동명 항목과 달라 별개로 분리됨 |

---

## 11. 전체 예시

`Customer` 가 Meta Type 두 개에 매핑된 형태까지 담았다. 같은 Object Type 이름으로 `objectMapping` 항목이 둘인 것이 정상이다.

```json
{
  "objectTypes": [
    {
      "name": "Customer",
      "description": "서비스를 이용하는 고객",
      "colorCode": "#4A90D9",
      "isPublic": true,
      "properties": [
        { "name": "id",        "dataType": "TEXT",     "orderNo": 1, "description": "고객 ID", "isTitleKey": false, "isPrimaryKey": true  },
        { "name": "name",      "dataType": "TEXT",     "orderNo": 2, "description": "고객명",  "isTitleKey": true,  "isPrimaryKey": false },
        { "name": "joined_at", "dataType": "DATETIME", "orderNo": 3, "description": "가입일시", "isTitleKey": false, "isPrimaryKey": false }
      ]
    },
    {
      "name": "Order",
      "description": "고객이 발생시킨 주문",
      "colorCode": "#F5A623",
      "isPublic": true,
      "properties": [
        { "name": "order_no",    "dataType": "TEXT",     "orderNo": 1, "description": "주문번호", "isTitleKey": true,  "isPrimaryKey": true  },
        { "name": "customer_id", "dataType": "TEXT",     "orderNo": 2, "description": "고객 ID",  "isTitleKey": false, "isPrimaryKey": false },
        { "name": "ordered_at",  "dataType": "DATETIME", "orderNo": 3, "description": "주문일시", "isTitleKey": false, "isPrimaryKey": false },
        { "name": "amount",      "dataType": "FLOAT8",   "orderNo": 4, "description": "주문금액", "isTitleKey": false, "isPrimaryKey": false }
      ]
    }
  ],
  "linkTypes": [
    {
      "name": "주문_고객",
      "description": "주문을 발생시킨 고객",
      "sourceObjectTypeName": "Order",
      "sourcePropertyName": "customer_id",
      "targetObjectTypeName": "Customer",
      "targetPropertyName": "id",
      "direct": "UNIDIRECTIONAL"
    }
  ],
  "metaTypes": [
    {
      "name": "고객마스터",
      "description": "CRM 고객 원천 테이블",
      "metaTypeKind": "CUSTOM",
      "properties": [
        { "name": "cust_id", "dataType": "TEXT",     "rawDataPropertyName": "CUST_ID", "description": "고객 ID" },
        { "name": "cust_nm", "dataType": "TEXT",     "rawDataPropertyName": "CUST_NM", "description": "고객명" },
        { "name": "reg_dt",  "dataType": "DATETIME", "rawDataPropertyName": "REG_DT",  "description": "등록일시" }
      ]
    },
    {
      "name": "멤버십회원",
      "description": null,
      "metaTypeKind": "CUSTOM",
      "properties": [
        { "name": "member_no",   "dataType": "TEXT",     "rawDataPropertyName": "member_no",   "description": null },
        { "name": "member_name", "dataType": "TEXT",     "rawDataPropertyName": "member_name", "description": null },
        { "name": "join_dt",     "dataType": "DATETIME", "rawDataPropertyName": "join_dt",     "description": null }
      ]
    },
    {
      "name": "주문원장",
      "description": "주문 원천 테이블",
      "metaTypeKind": "CUSTOM",
      "properties": [
        { "name": "ord_no",  "dataType": "TEXT",     "rawDataPropertyName": "ORD_NO",  "description": "주문번호" },
        { "name": "cust_id", "dataType": "TEXT",     "rawDataPropertyName": "CUST_ID", "description": "고객 ID" },
        { "name": "ord_dt",  "dataType": "DATETIME", "rawDataPropertyName": "ORD_DT",  "description": "주문일시" },
        { "name": "ord_amt", "dataType": "FLOAT8",   "rawDataPropertyName": "ORD_AMT", "description": "주문금액" }
      ]
    }
  ],
  "objectMapping": [
    {
      "objectTypeName": "Customer",
      "metaTypeName": "고객마스터",
      "propertyMappings": [
        { "objectTypePropertyName": "id",        "metaTypePropertyName": "cust_id" },
        { "objectTypePropertyName": "name",      "metaTypePropertyName": "cust_nm" },
        { "objectTypePropertyName": "joined_at", "metaTypePropertyName": "reg_dt" }
      ]
    },
    {
      "objectTypeName": "Customer",
      "metaTypeName": "멤버십회원",
      "propertyMappings": [
        { "objectTypePropertyName": "id",        "metaTypePropertyName": "member_no" },
        { "objectTypePropertyName": "name",      "metaTypePropertyName": "member_name" },
        { "objectTypePropertyName": "joined_at", "metaTypePropertyName": "join_dt" }
      ]
    },
    {
      "objectTypeName": "Order",
      "metaTypeName": "주문원장",
      "propertyMappings": [
        { "objectTypePropertyName": "order_no",    "metaTypePropertyName": "ord_no" },
        { "objectTypePropertyName": "customer_id", "metaTypePropertyName": "cust_id" },
        { "objectTypePropertyName": "ordered_at",  "metaTypePropertyName": "ord_dt" },
        { "objectTypePropertyName": "amount",      "metaTypePropertyName": "ord_amt" }
      ]
    }
  ]
}
```

---

## 12. 운영 반출물에 실제로 나타나는 형태

운영 온톨로지를 반출하면 아래가 함께 나타난다. 모두 규격이 허용하는 형태다. **읽을 때 놀라지 않기 위한 목록이고, 새로 만들 때 따라 할 목록이 아니다.**

| 형태 | 반입 결과 |
|---|---|
| `description` 이 `null`, `""`, 문자열 `"null"` | 그대로 저장 |
| `linkTypes[].targetObjectTypeName: null` (대상이 삭제된 관계) | 반입되되 `GOS61107`, 적용 차단 |
| 관계 이름 중복 (양끝은 다름) | 허용, 경고 `GOS61330` |
| 한 Object Type → 여러 Meta Type / 한 Meta Type ← 여러 Object Type | 정상 |
| 여러 속성이 같은 컬럼을 가리킴 | 정상 |
| `propertyMappings: []` | 반입되되 `GOS61016`, 적용 차단 |
| 식별 속성이 0개인 Object Type | 정상 (선택 항목) |
| 한글 이름, 밑줄로 이어 쓴 긴 이름 | 정상 |

그래서 **반출물을 그대로 다시 반입해도 검증 오류가 붙을 수 있다.** 파일이 잘못된 것이 아니라 운영 온톨로지에 이미 미완성 항목이 있었다는 뜻이다.
