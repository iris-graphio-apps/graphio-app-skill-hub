# 디자인 패턴 목록

온톨로지 디자인 패턴의 여섯 계열, 패턴을 고르고 적용하는 절차(eXtreme Design), 안티패턴, 출처를 정리한 참고 문서다. 이 스킬의 흐름 단계마다 어느 계열을 어떻게 쓰는지는 10장에 둔다.

**③~⑤에서 꼴을 고를 때 펴는 문서는 [`structure-patterns.md`](structure-patterns.md)다.** 이 문서는 그 꼴의 근거(원래 패턴의 뜻·역량 질문·한계)를 볼 때 편다. [`structure-patterns.md`](structure-patterns.md) 3.1 꼴 목록 표 '꼴 이름(원래 이름)' 칸의 괄호가 이 문서의 절을 가리킨다.

**이 문서의 패턴 이름(원래 이름)은 설계 리포트와 대화 출력에 적지 않는다.** 원래 이름은 모델이 읽는 참고 문서에만 둔다.

---

## 1. 핵심 정리와 여섯 계열

온톨로지 디자인 패턴(Ontology Design Pattern, ODP)은 **온톨로지를 설계할 때 거듭 부딪히는 문제를 풀어 두고 다시 쓰는 해법**이다. OWL 코드 조각만 가리키지 않고, 아래 요소를 함께 갖춘다.

- 어떤 문제를 푸는지 밝힌 의도(Intent)
- 온톨로지가 답해야 할 역량 질문(Competency Questions)
- 클래스·속성·공리 구조
- 적용 예와 사용 조건
- 장점과 제약
- 관련 패턴과 다시 쓸 수 있는 OWL 구현

ODP 공식 분류는 크게 **6개 계열**이다. 실무에서 “ODP를 적용한다”고 하면 대개 콘텐츠 ODP를 가리킨다. 그러나 실제 온톨로지 개발에서는 나머지 계열도 함께 쓴다. [Gangemi와 Presutti의 ODP 분류 문서](https://www.researchgate.net/profile/Aldo-Gangemi/publication/227215903_Ontology_Design_Patterns/links/00b7d5152eea4d92eb000000/Ontology-Design-Patterns.pdf), [ODPA 공식 사이트](https://odpa.github.io/)

| ODP 계열 | 푸는 문제 | 주요 하위 유형 |
|---|---|---|
| Structural ODP | 온톨로지의 논리 구조와 전체 구조를 어떻게 설계할 것인가 | Logical, Architectural |
| Correspondence ODP | 기존 모델을 변환하거나 서로 다른 온톨로지를 잇는 방법 | Reengineering, Mapping/Alignment |
| Content ODP | 역할·사건·시간·장소·부분 관계 같은 도메인 개념을 모델링하는 방법 | 개별 콘텐츠 패턴 여럿 |
| Reasoning ODP | 원하는 추론 결과를 얻도록 공리를 짜는 방법 | 하위 유형 없음. 등재된 패턴도 사실상 없음(5장) |
| Presentation ODP | 사람이 읽고 이해하고 다시 쓰기 쉬운 온톨로지를 만드는 방법 | Naming, Annotation |
| Lexico-Syntactic ODP | 자연어 표현을 온톨로지 구조에 잇는 방법 | 문장·어휘 패턴 |

**포털 위키(ontologydesignpatterns.org)는 지금도 운영 중이다. 다만 HTTP로만 열린다.** 2026년 9월 21일 기준으로 `http://ontologydesignpatterns.org`는 정상 응답하고, `https://`는 응답하지 않는다. 접속이 안 된다는 보고는 대개 이 때문이다. 브라우저가 주소를 HTTPS로 자동으로 바꾸면 열리지 않는다.

패턴마다 붙은 **의도·역량 질문·결과·시나리오·재사용 OWL 블록**이 개별 페이지에 그대로 있다. 이 문서의 역량 질문은 거기서 가져왔다. MediaWiki API도 열려 있어 `api.php`로 목록과 본문을 받을 수 있다.

| 주소 | 내용 |
|---|---|
| `index.php/OPTypes` | 여섯 계열 분류 |
| `index.php/Submissions:<패턴이름>` | 패턴 개별 페이지 |
| `index.php/Category:<계열>OP` | 계열별 등재 목록 |
| `api.php?action=query&list=allpages&apnamespace=500` | 제출된 패턴 전체 목록 |

다만 **일부 목록이 비어 보인다.** 개수를 세는 질의가 0을 돌려주고 `Category:ContentOP` 하위 목록도 비어 있다. 그래도 패턴 페이지는 정상으로 열린다. 목록이 비었다고 패턴이 없다고 읽으면 안 된다. 제출 이름 공간에는 최상위 페이지만 259개 있다.

같은 내용을 후속 조직인 ODPA가 [패턴 저장소](https://github.com/odpa/patterns-repository)에도 옮겨 두었다. 이 분류는 NeOn 프로젝트 산출물에서 나왔고, 포털이 그대로 채택했다. 분류를 가장 자세히 풀어 둔 문헌은 [Hammar의 박사학위논문](http://liu.diva-portal.org/smash/get/diva2:1131672/FULLTEXT02) 2장이다.

---

## 2. 구조 패턴

온톨로지가 **논리 구조가 어떤 모양이어야 하는가**를 다룬다(Structural ODP). 도메인의 뜻보다 표현 방식과 전체 아키텍처에 무게를 둔다.

### 2.1 논리 패턴

OWL이나 RDF 같은 표현 언어로 특정 논리 구조를 나타낼 때 쓴다(Logical ODP). 도메인과 무관하므로 `Person`, `Product` 같은 개별 개념이 아니라 클래스·속성·제약을 어떻게 조합할지를 정한다.

#### Logical Macro

자주 되풀이되는 논리식 조합을 설계 단위 하나처럼 묶어 쓰는 패턴이다.

예를 들어 아래 두 조건은 뜻이 다르다.

- `allValuesFrom`: 값이 있다면 모두 특정 클래스여야 한다.
- `someValuesFrom`: 특정 클래스의 값이 적어도 하나 있어야 한다.

`allValuesFrom`만 걸면 관계가 실제로 있다는 뜻이 되지 않는다. “모든 직원은 적어도 한 조직에 소속되고, 소속 대상은 조직이어야 한다”를 나타내려면 두 제약을 함께 걸어야 한다.

#### Transformation Pattern

OWL처럼 표현력이 제한된 언어로는 바로 적을 수 없는 논리 구조를, 그 언어로 적을 수 있는 구조로 바꾼다.

대표 사례가 **N항 관계(n-ary relation) 패턴**이다. RDF/OWL 속성은 두 대상만 잇기 때문에 “회사 A가 2026년 9월 21일 서울에서 제품 X를 발표했다.” 같은 관계를 속성 하나로 나타낼 수 없다.

그래서 관계 자체를 개체로 만든다.

```turtle
:announcement1 a :Announcement ;
    :announcedBy :CompanyA ;
    :announces :ProductX ;
    :announcementDate "2026-09-21"^^xsd:date ;
    :announcementPlace :Seoul .
```

이렇게 하면 날짜·장소·발표자·신뢰도처럼 관계에 붙는 부가 정보를 적을 수 있다. 대신 노드가 늘고 조회 경로가 길어지므로, 단순한 이항 관계에는 쓰지 않는 편이 좋다.

W3C 노트는 해결책을 **두 가지**로 정리하고, 첫째 해결책을 쓰는 경우를 다시 셋으로 나눈다. [W3C N-ary Relations 패턴](https://www.w3.org/TR/swbp-n-aryRelations/)

| 해결책 | 쓰는 경우 |
|---|---|
| 관계를 클래스로 만든다 | 관계 자체에 부가 정보가 붙을 때 · 한 관계가 여러 측면을 가질 때 · 주된 참여자를 하나로 꼽을 수 없을 때(구매 거래처럼 구매자·판매자·물품·금액이 대등할 때) |
| 인자를 순서 목록으로 만든다 | 참여자마다 다른 역할 없이 순서만 있을 때(예: 항공편 경유지 순서) |

노트는 RDF 구체화(reification)를 쓰지 않는 까닭도 밝힌다. 부가 정보는 **진술문을 설명하는 정보가 아니라 관계 인스턴스 자체의 정보**이기 때문이다.

치르는 대가도 셋 적혀 있다.

- OWL이 제공하는 구성요소를 그대로 쓰기 어려워진다.
- 조건이 붙을 때마다 클래스 계층이 늘어난다.
- 역관계를 관계마다 따로 정의해야 한다.

#### Class as Property Value

클래스 자체를 속성값으로 쓰고 싶은 경우다. “이 책의 주제는 사자다”에서 주제는 사자 한 마리가 아니라 `Lion` 클래스다. OWL DL과 OWL Lite는 이것을 막으므로 돌아가는 방법을 써야 한다. W3C는 그 방법 다섯 가지를 견준다. [W3C Classes as Values 패턴](https://www.w3.org/TR/swbp-classes-as-values/)

| 방법 | 얻는 것 | 잃는 것 |
|---|---|---|
| 클래스를 그대로 값으로 쓴다 | 가장 간결하고, 하위 클래스 관계가 그대로 추론된다 | OWL Full과 RDFS에서만 쓸 수 있다 |
| 클래스의 대표 인스턴스를 값으로 쓴다 | OWL DL에서 쓸 수 있다 | 원래 온톨로지를 다시 쓸 때 의도가 부딪히고, 두 계층의 이어짐이 정의에 드러나지 않는다 |
| 주제 계층을 따로 만든다 | OWL DL에서 쓸 수 있고, 주제 체계와 개념 체계가 분리된다 | 계층 두 개를 관리해야 한다 |
| 제한 조건으로 바꿔 쓴다 | OWL DL에 완전히 맞고 자동 분류가 된다 | “클래스 자체”가 “불특정 개체”로 뜻이 바뀌어 읽기 어려워진다 |
| 주석 속성으로 쓴다 | OWL DL에 맞으면서 첫째 방법처럼 직접 쓸 수 있다 | 추론에 전혀 쓰이지 않고, 값의 범위나 개수를 제한할 수 없다 |

#### Value Partition과 Value Set

속성이 가질 수 있는 값을 정해진 범위로 묶는 문제다. “건강 상태는 양호·보통·불량 셋 중 하나” 같은 경우다. 방법은 두 가지다. W3C는 **한 온톨로지 안에서 둘을 섞지 말라**고 권한다. [W3C Specified Values 패턴](https://www.w3.org/TR/swbp-specified-values/)

| 방법 | 방식 | 장단점 |
|---|---|---|
| Value Set | 값을 개체로 열거한다(`owl:oneOf`와 `owl:differentFrom`) | 데이터베이스의 코드 테이블과 닮아 이해하기 쉽다. 대신 값을 더 잘게 나눌 수 없고, 여러 축으로 나눌 수도 없다 |
| Value Partition | 값을 클래스로 나눈다(`owl:unionOf` · `owl:disjointWith` · `owl:FunctionalProperty`) | OWL DL에 맞고, 나중에 값을 더 나눌 수 있다. 대신 값이 n개면 배타성 공리가 n(n−1)/2개로 불어난다 |

W3C는 기술 면에서 Value Partition 쪽이 더 낫다고 본다.

#### Partition

상위 개념을 서로 겹치지 않는 하위 개념으로 빠짐없이 나누는 패턴이다. 위의 Value Partition이 속성값을 나눈다면, 이 패턴은 개념 계층 자체를 나눈다.

```
EquivalentClasses(P, ObjectUnionOf(C1, ..., Cn))
DisjointClasses(C1, ..., Cn)
```

두 줄이 함께 있어야 분할이다. 합집합만 선언하면 “빠짐없이 나눴다”만 말하고, 배타성만 선언하면 “겹치지 않는다”만 말한다.

#### Tree

계층 구조를 다루는 논리 패턴이다. 포털에 `Tree Pattern`으로 등재되어 있다. 순서 있는 목록(`List`)과 모음(`Set`·`Bag`)은 논리 패턴이 아니라 **콘텐츠 패턴**으로 등재되어 있다. 그 역량 질문은 4.2에 있다.

#### Normalisation

여러 축이 뒤섞인 다중 상속 계층을 축마다 독립된 원시 계층으로 갈라 두고, 제한 조건으로 다시 묶는 방법이다. 포털은 그 결과를 “온톨로지가 깔끔한 모듈 여러 개로 나뉜다. 나머지 의미는 그 모듈을 가리키는 제한 조건이 맡는다. 다중 계층을 사람이 손으로 관리하다 틀리는 대신, 추론기가 구조를 유지한다.”라고 적었다.

원안은 Rector의 2003년 논문(DOI `10.1145/945645.945664`)이다. **그 논문 전문은 확인하지 못했다.** 위 인용은 포털 등재 항목에서 가져왔다.

#### 포털에 등재된 논리 패턴 전체

`Category:LogicalOP`에 18개가 등재되어 있다. 위에서 다룬 것 말고도 아래 패턴이 있다.

| 패턴 | 다루는 문제 |
|---|---|
| N-Ary Relation Pattern (OWL 2) | OWL 2에서 N항 관계를 다루는 판 |
| Symmetric n-ary relationship · Summarization of an inverse n-ary relation | N항 관계의 대칭·역방향 변형 |
| Context Slices | 맥락마다 달라지는 사실을 조각으로 나눈다 |
| Change of Time Varying Entities | 시간에 따라 변하는 개체를 다룬다 |
| NegativePropertyAssertions | 어떤 관계가 성립하지 않는다는 사실을 적는다 |
| Create Disjoint Siblings · Define Hybrid Class · Enlarge Class Definition | 서로 겹치지 않아야 할 형제 개념이 겹친 계층을 고치는 세 가지 방법 |
| Stub Metapattern | 다른 패턴을 끼울 자리를 남겨 두는 뼈대 |

**주의할 점이 하나 있다.** 9장 안티패턴에 나오는 OIL·SOE·DOC 세 가지도 이 목록에 논리 패턴으로 함께 등재되어 있다. 포털에는 안티패턴 전용 분류가 없다. 이름만 보고 권장 패턴으로 오해하면 안 된다.

### 2.2 아키텍처 패턴

개별 관계가 아니라 온톨로지 전체를 어떻게 구성할지 정한다(Architectural ODP).

- **내부 아키텍처 패턴**: 쓸 논리 구조나 OWL 표현 범위를 제한한다. 추론 성능을 위해 특정 OWL 프로파일에 맞추는 방식이 그 예다.
- **외부 아키텍처 패턴**: 거대한 온톨로지 하나 대신 도메인별 모듈을 만들고 `owl:imports`로 잇는 구조다.

보도자료를 다루는 온톨로지라면 아래처럼 나눈다.

- `core.owl`: 공통 Entity, Event, Time
- `organization.owl`: Company, Person, Role
- `document.owl`: Document, File, InformationObject
- `press-release.owl`: PressRelease, Quote, Announcement

고칠 때 영향이 미치는 범위가 좁아지고, 모듈을 따로 다시 쓰기 쉬워진다. 대신 `owl:imports`가 순환하지 않는지, 모듈 사이에 같은 정의가 겹치지 않는지 관리해야 한다.

---

## 3. 대응 패턴

이미 있는 데이터 모델이나 온톨로지 사이의 **변환과 연결**을 다룬다(Correspondence ODP).

### 3.1 재공학 패턴

기존 자원을 새 온톨로지로 바꾸는 규칙이다(Reengineering ODP). 원본은 데이터베이스 스키마, UML, 분류체계, 시소러스, 기존 온톨로지 가운데 무엇이든 될 수 있다.

#### Schema Reengineering

온톨로지가 아닌 모델을 OWL 온톨로지로 바꾼다.

예:

| 기존 구조 | 바꾼 온톨로지 구조 |
|---|---|
| `COMPANY` 테이블 | `Company` 클래스 |
| `CEO_ID` 외래 키 | `hasCEO` 객체 속성 |
| 분류코드 테이블 | SKOS Concept 또는 OWL 클래스 |
| UML association | OWL ObjectProperty |

스키마를 구조 그대로 옮기기만 해서는 뜻이 보존되지 않는다. 데이터베이스의 외래 키가 늘 현실의 의미 관계와 맞아떨어지지는 않기 때문이다.

포털에 등재된 재공학 패턴은 12개다. **대부분이 분류체계와 시소러스를 옮기는 패턴**이다. 같은 분류체계라도 원본을 어떤 데이터 모델로 저장했는지에 따라 패턴이 갈린다.

| 원본 저장 방식 | 옮기는 패턴 |
|---|---|
| 인접 목록(adjacency list) | 분류체계 → 분류 계층(taxonomy) |
| 경로 열거(path enumeration) | 분류체계 → 분류 계층(taxonomy) |
| 평탄화(flattened) · 눈송이(snowflake) | 분류체계 → 온톨로지 스키마 |
| 레코드 기반 · 관계 기반 | 용어 시소러스 → 온톨로지 스키마 |

같은 뜻의 계층이라도 **원본이 부모를 적어 둔 방식이 다르면 변환 규칙이 다르다.** 관계형 원본을 다룰 때 이 구분이 쓸모 있다. 이 밖에 `Faceted Classification Scheme`, `CyclicSubClassOf`, `Xsd:sequence embedding`이 등재되어 있다.

#### Refactoring

기존 온톨로지의 뜻을 되도록 유지하면서 구조를 개선한다.

처음에 아래 이항 관계가 있었다고 하자.

```text
Person ──prepares──> Coffee
```

나중에 시간과 도구까지 저장해야 한다면 `prepares`를 단순 속성으로 둘 수 없다. 이 관계를 `CoffeePreparation`이라는 사건 클래스나 상황 클래스로 다시 짠다.

```text
CoffeePreparation
 ├─ hasAgent → Person
 ├─ hasObject → Coffee
 ├─ usesTool → Tool
 └─ occursAt → TimeInterval
```

N항 논리 패턴을 기존 모델에 적용하는 이 과정 전체가 Refactoring ODP다.

### 3.2 매핑·정렬 패턴

두 온톨로지의 기존 요소는 그대로 두고, 의미상 대응 관계만 선언한다(Mapping/Alignment ODP). 초기 문헌은 주로 `Mapping ODP`, 포털은 `Alignment ODP`라는 이름을 쓴다.

대표 대응 관계는 아래와 같다.

- 동등: 두 클래스나 속성의 뜻이 같다
- 포함·포섭: 한 개념이 다른 개념보다 구체적이다
- 중첩: 일부 인스턴스를 공유할 수 있다
- 비동등·비포함·분리: 서로 다르거나 양립할 수 없다

예:

```turtle
:Company owl:equivalentClass schema:Organization .
:PressRelease rdfs:subClassOf schema:DigitalDocument .
```

`owl:equivalentClass`는 “이름이 비슷하다”는 뜻이 아니다. 두 클래스가 **양방향으로 논리상 같다**고 선언한다. 뜻이 완전히 같지 않다면 `rdfs:subClassOf`, SKOS 매핑 속성, 별도의 연결용 온톨로지(bridge ontology) 가운데 하나를 쓰는 편이 안전하다.

포털 `Category:AlignmentOP`에 14개가 등재되어 있다. 대응 관계의 **모양별로** 하나씩 두었다.

| 패턴 | 대응 모양 |
|---|---|
| Class equivalence | 두 클래스가 같다 |
| Class subsumption | 한쪽이 다른 쪽에 포함된다 |
| Class intersection · Class Union | 교집합·합집합으로 대응한다 |
| Disjoint Classes | 서로 겹치지 않는다 |
| Class by attribute value · by attribute type · by attribute occurence · by path attribute value | 상대 클래스를 속성값·속성 유형·속성 유무·경로로 정의해 맞춘다 |
| Class correspondence defined by relation domain | 관계의 정의역으로 클래스를 맞춘다 |
| Vocabulary Alignment Pattern(외부 클래스의 하위 클래스 · 외부 속성의 하위 속성 · 외부 클래스의 공동 인스턴스) | 외부 어휘를 건드리지 않고 자기 쪽에서 잇는다 |

실무에서는 마지막 묶음을 가장 자주 쓴다. 남의 온톨로지를 고칠 수 없을 때 쓰는 방법이다.

---

## 4. 콘텐츠 패턴

도메인에서 되풀이되는 개념 모델링 문제를 푸는 작은 온톨로지 모듈이다(Content ODP). 분류를 제안한 저자들은 콘텐츠 패턴이 대개 클래스 2~10개로 이루어진 작고 독립된 구성요소라고 설명한다.

[`structure-patterns.md`](structure-patterns.md) 3.1 꼴 목록의 원래 이름 괄호가 가리키는 이 문서의 절은 아래와 같다.

| `structure-patterns.md` 3.1 No. | 꼴 이름(원래 이름) | 이 문서의 절 |
|---|---|---|
| 1 | 참여 사건(Participation·Situation) | 4.1, 4.2 |
| 2 | 역할 관계(AgentRole·ParticipantRole) | 4.1, 4.2 |
| 3 | 구성 가운데 개념(Componency·N항 관계) | 4.2, 4.3, 2.1(N항 관계) |
| 4 | 절차 차례(Sequence) | 4.1, 4.2 |
| 5 | 소속·위치(Constituency·Place·PartOf) | 4.1, 4.2, 4.3 |
| 6 | 분류 코드(Classification·Value Set) | 4.1, 4.2, 2.1(Value Partition과 Value Set) |
| 7 | 목록 펼침(Collection 항목만) | 4.1, 4.2, 4.3 |
| 8 | 식별자 대응(Mapping의 데이터판) | 3.2 |
| 9 | 정보 실현(Information realization) | 4.1, 4.2 |
| 10 | 시점 색인(Time indexed participation·TimeIndexedSituation·Transition) | 4.1, 4.2 |
| 11 | 경유 연결(조인 경로) | 해당 절 없음(원래 이름이 디자인 패턴이 아님) |

콘텐츠 패턴을 다루는 일은 두 층으로 나뉜다. **패턴을 만들어 내는 일**과 **만든 패턴을 내 온톨로지에 넣는 일**은 다른 일이다.

**패턴을 만드는 방법**은 NeOn 프로젝트가 네 가지로 정리했다.

| 방법 | 하는 일 |
|---|---|
| Reengineering | 다른 데이터 모델에서 패턴을 뽑아낸다 |
| Specialization · Composition | 이미 있는 패턴을 특수화하거나 여러 개를 엮는다 |
| Extraction | 참조 온톨로지에서 되풀이되는 조각을 떼어낸다 |
| 순차 결합 | 떼어낸 뒤 특수화·일반화·확장을 차례로 거친다 |

**패턴을 온톨로지에 넣는 방법**은 두 가지로 갈린다. 문헌이 실제로 견주는 것은 이 두 방법이다.

| 방법 | 방식 | 장단점 |
|---|---|---|
| 특수화(specialisation-based) | `owl:imports`로 패턴을 그대로 들여온 뒤, 하위 클래스와 하위 속성을 만들어 도메인의 뜻을 붙인다 | 같은 이름 공간을 쓰므로 다른 데이터와 그대로 맞물린다. 대신 `Situation`·`Agent` 같은 범위가 넓은 상위 개념이 함께 들어온다. 도메인 전문가는 그 개념이 왜 필요한지 납득하지 못하기도 한다 |
| 복제(template-based) | 패턴의 클래스와 속성을 복사해 이름을 바꾸고 내 이름 공간에 둔다 | 읽기 쉽고 고치기 쉽다. 대신 상위 정의가 여러 온톨로지에 중복되고, 이름 공간이 달라져 다른 온톨로지와 함께 쓰기 어려워진다 |

특수화 방식은 다시 둘로 갈린다. 하나는 **하위 속성을 새로 정의하는 쪽**이다. 다른 하나는 **원래 속성을 그대로 쓰되 하위 클래스에 `allValuesFrom`·`someValuesFrom` 제한을 거는 쪽**이다. 실측해 보니 앞쪽이 사용성과 추론 성능 모두 나았다. 같은 벤치마크에서 뒤쪽이 네 시간 넘게 걸린 작업을 앞쪽은 2초 안에 끝냈다. 뒤쪽은 원래 속성 이름을 그대로 쓰므로 데이터셋끼리 바로 맞물린다는 장점이 있다. [Hammar (2017) 5장](http://liu.diva-portal.org/smash/get/diva2:1131672/FULLTEXT02)

콘텐츠 패턴은 이름이 아니라 **역량 질문**으로 고른다. 예를 들어 “누가 어떤 역할을 언제 맡았는가?”에 답해야 한다면, 단순한 Agent–Role보다 Time-Indexed Role 패턴이 맞다. [Springer의 Pattern-Based Ontology Design](https://link.springer.com/chapter/10.1007/978-3-642-24794-1_3)

### 4.1 주요 콘텐츠 패턴

| 패턴 | 푸는 문제 | 설명과 주의점 |
|---|---|---|
| Participation | 어떤 객체가 어떤 사건에 참여했는가 | `Object—participatesIn→Event` 구조다. 기본 패턴에는 참여 시점이 없으므로, 시점이 필요하면 Time-Indexed Participation을 쓴다. [공식 Participation 패턴](https://odpa.github.io/patterns-repository/Participation/Participation) |
| AgentRole | 어떤 행위자가 어떤 역할을 맡는가 | 사람과 역할을 분리한다. 같은 사람이 CEO·발표자·저자 역할을 동시에 맡을 수 있다. 기본형은 역할의 유효 기간을 나타내지 않는다. |
| Time-Indexed Person Role | 누가 언제 어떤 역할을 맡았는가 | Person, Role, TimeInterval을 하나의 상황으로 잇는다. 과거 CEO나 프로젝트 기간의 책임자처럼 역할이 시간에 따라 달라질 때 쓴다. [공식 패턴 정의](https://github.com/odpa/patterns-repository/blob/master/Time_indexed_person_role/Time_indexed_person_role.md?plain=1) |
| Information Realization | 추상 정보와 구체 매체를 어떻게 구분하는가 | “보도자료의 내용”과 PDF·HTML·인쇄본을 따로 모델링한다. 같은 내용이 여러 파일 형식으로 실현될 수 있다. |
| Situation | 관계가 성립하는 맥락을 어떻게 나타내는가 | 시간·장소·관점·원인이 결합된 맥락을 Situation 개체 하나로 만든다. 복잡한 N항 관계에 맥락을 붙일 때 쓴다. |
| Time-Indexed Situation | 특정 상황이 언제 성립했는가 | Situation과 TimeInterval을 결합한 패턴이다. 주소·소속·상태처럼 시간에 따라 변하는 것에 맞다. |
| Classification | 개체에 어떤 개념·범주를 부여했는가 | 태그·역할·분류체계의 개념을 일급 객체로 만들어 개체를 분류한다. 분류 주체·기준·시간이 필요하면 Situation 패턴과 결합해야 한다. |
| Place | 어떤 대상이 어디에 있는가 | 일반 위치 관계를 나타낸다. 물리적 위치인지 행정구역인지 밝히려면 더 나눠야 한다. 위치가 시간에 따라 변하면 시간 패턴과 결합해야 한다. |
| Sequence | 무엇이 무엇보다 앞서거나 바로 다음에 오는가 | `precedes`와 `directlyPrecedes`를 구분한다. 작업 흐름, 사건 순서, 문서 절 순서에 쓴다. |
| CollectionEntity | 어떤 것이 어떤 모음의 구성원인가 | 모음의 구성원 관계는 부분–전체 관계와 다르다. 팀 구성원, 문서 묶음, 데이터셋 집합을 나타낸다. |

### 4.2 역량 질문으로 고르는 표

**패턴은 이름이 아니라 역량 질문으로 고른다.** 지금 답해야 하는 질문과 모양이 같은 줄을 찾으면 그것이 후보다. 아래 표는 포털의 각 패턴 페이지가 적어 둔 역량 질문을 옮긴 것이다. **역량 질문 칸이 비어 있는 패턴은 의도문으로 대신했고, 그 자리에 표시해 두었다.**

**참여**

| 패턴 | 역량 질문 | 한계 |
|---|---|---|
| Participation | 이 사건에 어떤 객체가 참여했는가 · 이 객체는 어떤 사건에 참여했는가 | 시점이 없다 |
| Time indexed participation | 언제 무엇이 그 사건에 참여했는가 · 그 사건에 어느 시점에 누가 참여했는가 | 한 개체가 한 사건에 참여하는 것만 다룬다 |
| Nary Participation | 그 사건에 이 시점에 참여한 것은 무엇인가 · 그 장소에서 어떤 사건에 누가 참여했는가 | 참여 시점이나 관여한 부분이 다르면 건을 나눠야 한다 |
| Co-participation | 같은 사건에 함께 참여한 객체는 무엇인가 · 누가 누구와 함께 있었는가 | — |

**역할**

| 패턴 | 역량 질문 | 한계 |
|---|---|---|
| AgentRole | 어떤 행위자가 이 역할을 맡는가 · 그 행위자가 맡는 역할은 무엇인가 | 역할의 기간을 나타내지 못한다 |
| Objectrole | 이 객체는 어떤 역할을 맡는가 · 그 역할을 맡는 객체는 무엇인가 | 위와 같다. 행위자가 아닌 사물까지 다룬다 |
| ParticipantRole | 이 사건에서 이 객체의 역할은 무엇인가 · 이 역할을 맡은 객체는 무엇인가 · 이 객체가 그 역할을 맡은 사건은 무엇인가 | 시점을 다루지 않는다 |
| Time indexed person role | (역량 질문 칸이 비어 있다) 의도 — 어느 시점에 무엇이 어떻게 분류되는지를 나타낸다 | — |
| Role task | 이 작업은 어느 역할의 것인가 · 이 역할은 어떤 작업을 하는가 | 작업 배정의 시점을 다루지 못한다 |

**맥락과 분류**

| 패턴 | 역량 질문 | 한계 |
|---|---|---|
| Situation | 무엇의 맥락·상황은 무엇인가 · 이 맥락에 있는 것은 무엇인가 | — |
| Description | 무엇을 어떤 전제 아래 기술했는가 · 그 기술에 관여한 개념은 무엇인가 | — |
| TimeIndexedSituation | 그 상황은 언제 성립했는가 · 그 시점에 성립한 상황은 무엇인가 | — |
| Classification | 이 개체에 어떤 개념이 부여됐는가 · 이 개체는 어느 범주에 드는가 | 분류의 주체·기준·시점은 담기지 않는다 |
| Types of entities | 그것은 어떤 종류의 개체인가 · 사건인가 객체인가 · 값인가 성질인가 | — |
| Object with states | (역량 질문 칸에 제약 목록이 적혀 있다) 의도 — 객체의 상태와 상태마다 걸리는 제약을 나타낸다 | 상태를 값이 아니라 개체로 두어야 한다 |

**부분·모음**

| 패턴 | 역량 질문 | 한계 |
|---|---|---|
| PartOf | 이것은 무엇의 부분인가 · 이것의 부분은 무엇인가 | 시점을 담지 못한다. A가 B의 부분이고 B가 C의 부분이면 A도 C의 부분이 된다 |
| Componency | 이 객체는 무엇의 구성요소인가 · 이 객체의 구성요소는 무엇인가 | 진부분 관계는 추이적이지 않다 |
| Constituency | 이 개체의 구성물은 무엇인가 · 이것은 무엇을 이루는가 | 물리 대상이 비물리 대상을 이루는 경우를 다룬다 |
| TimeIndexedPartOf | 언제 이것이 저것의 부분이었는가 · 그 시점에 이것의 부분은 무엇인가 | — |
| Collection · CollectionEntity | 이 모음에 든 것은 무엇인가 · 이것은 어느 모음의 구성원인가 | 시점이 붙은 소속은 담지 못한다 |
| Set | 이 집합의 크기는 얼마인가 · 원소는 무엇인가 | 중복을 허용하지 않는다 |
| Bag | 이 항목은 어느 묶음의 것인가 · 묶음의 크기는 얼마인가 | 중복을 허용한다 |
| List | 이 목록의 항목은 무엇인가 · 길이는 얼마인가 · 첫째와 마지막은 무엇인가 · 다음과 이전은 무엇인가 | — |

**순서와 변화**

| 패턴 | 역량 질문 | 한계 |
|---|---|---|
| Sequence | 무엇이 무엇보다 앞서는가 · 다음은 무엇인가 · 바로 다음은 무엇인가 | 되돌아오는 순환은 나타내지 못한다 |
| Transition | 어떤 사건이 그 객체의 어떤 상태를 바꿨는가 · 전이를 거쳐도 변하지 않는 과정은 무엇인가 | — |
| Action | 이 행동은 무엇에 달려 있는가 · 언제 시작하고 끝났는가 · 지금 상태는 무엇인가 | 상태와 분류가 어긋나도 막지 않는다 |
| TaskExecution | 이 행동으로 어떤 작업이 수행되는가 · 그 작업을 하려면 어떤 행동을 하는가 | — |

**값·장소·시간**

| 패턴 | 역량 질문 | 한계 |
|---|---|---|
| Region | 그 개체의 속성값은 무엇인가 · 그 값을 갖는 개체는 무엇인가 | — |
| Place | 어떤 것이 어디에 있는가 · 이 장소에 있는 것은 무엇인가 | 어떤 종류의 위치인지 정하지 않는다. 시점도 없다 |
| TimeInterval | 이 구간의 시작과 끝은 언제인가 | 날짜는 값일 뿐 논의 대상이 아니다. 필요하면 Region과 엮는다 |
| TimePeriod | 기간의 단위는 무엇이고 값은 얼마인가 | — |

**정보와 문서**

| 패턴 | 역량 질문 | 한계 |
|---|---|---|
| Information realization | 이 정보 객체의 물리적 실현물은 무엇인가 · 이 물리 객체가 실현하는 정보 객체는 무엇인가 | — |
| IntensionExtension | 이 정보 객체의 뜻은 무엇인가 · 무엇에 관한 것인가 | — |
| Tagging | 누가 어떤 어휘의 어떤 말로 무엇에 꼬리표를 달았는가 | — |
| Observation | 무엇이 관측됐는가 · 어떤 조건에서 관측했는가 | — |
| Literal Reification | 그 값이 쓰인 맥락은 무엇인가 · 그 맥락에서 값의 뜻은 무엇인가 | — |

**고를 때는 표의 「한계」 칸을 본다.** 지금 질문이 그 패턴이 못 하는 것을 요구하면, 그 한계를 메운 다음 패턴으로 옮겨 간다. Participation → Time indexed participation → Nary Participation 순서가 그 예다.

포털에는 이 밖에 특정 도메인용 패턴이 100개 넘게 있다. 범용 패턴을 찾을 때는 도메인 패턴을 걸러 내야 한다.

### 4.3 부분–전체 패턴 네 가지의 차이

이 네 패턴은 특히 헷갈리기 쉽다.

| 패턴 | 뜻 | 추이성 | 예 |
|---|---|---|---|
| PartOf | 일반 부분–전체 관계 | 있음 | 심장은 인체의 부분이다 |
| Componency | 대상을 직접 이루며 기능을 맡는 구성요소 | 없음 | 배터리는 자동차의 직접 구성요소다 |
| Constituency | 서로 다른 존재 층위의 구성 관계 | 대개 따로 다룸 | 사람이 조직을 구성한다, 목재가 탁자를 구성한다 |
| CollectionEntity | 모음의 구성원 관계 | 없음 | 파일 A는 문서 모음의 구성원이다 |

`PartOf`를 모든 부분 관계에 쓰면 추이성 때문에 원치 않는 결론이 나올 수 있다. 예를 들어 “나사가 엔진의 구성요소이고, 엔진이 자동차의 구성요소”라고 해서 실무 질의에서 나사를 자동차의 **직접 구성요소**로 다루면 안 된다. 그래서 `PartOf`와 `Componency`를 구분한다. [공식 Componency 패턴](https://odpa.github.io/patterns-repository/Componency/Componency)

---

## 5. 추론 패턴

추론 엔진이 원하는 결과를 내도록 논리 패턴을 짜는 방법이다(Reasoning ODP).

대표 목적은 아래와 같다.

- **Classification**: 개체나 클래스를 조건에 따라 자동 분류
- **Subsumption**: 클래스 사이의 상위·하위 관계 계산
- **Inheritance**: 상위 클래스의 제약과 특성 상속
- **Materialization**: 추론으로만 드러나는 사실을 트리플로 직접 저장
- **Normalization**: 복잡한 다중 상속 구조를 제약 기반 구조로 정규화
- **De-anonymizing**: 익명 클래스 표현에 이름을 붙여 다루기 쉽게 전환

예를 들어 `TechnicalPressRelease`를 개체마다 직접 붙이지 않고 아래 조건으로 정의한다.

```text
PressRelease
AND announces some Technology
AND hasTechnicalComponent some TechnicalComponent
```

추론기는 이 조건을 만족하는 보도자료를 자동으로 `TechnicalPressRelease`로 분류한다.

Logical ODP가 “이 논리를 OWL로 어떻게 적을까”를 묻는다면, Reasoning ODP는 “그렇게 적은 것으로 어떤 추론 결과를 얻을까”를 묻는다. 추론 성능, OWL 프로파일, 열린 세계 가정(Open World Assumption)도 함께 따져야 한다.

**다만 이 계열에는 등재된 패턴이 하나도 없다.** 포털의 `Category:ReasoningOP`가 비어 있다. 분류를 가장 자세히 정리한 문헌도 2017년 기준으로 “이 정의에 들어맞는 Reasoning 패턴이 출판된 사례가 없다”고 적었다. 여섯 계열 가운데 이름만 있고 등재된 패턴이 없는 계열이다.

위 목록은 분류를 제안한 저자들이 **여기에 무엇이 올 수 있는지 예로 든 것**이지, 등재된 패턴 이름이 아니다. Normalization은 예로 자주 거론되지만 포털에는 Logical ODP로 등재되어 있다.

---

## 6. 표현 패턴

온톨로지의 논리적 뜻이 아니라, **읽고 이해하고 배포하고 다시 쓰기 쉽게** 만드는 일을 다룬다(Presentation ODP).

### 6.1 이름 짓기 패턴

IRI·이름 공간·클래스·속성·파일·버전의 이름을 짓는 규칙이다(Naming ODP).

예:

- 클래스: `PressRelease`, `TechnicalComponent`
- 객체 속성: `announcesProduct`, `hasSpokesperson`
- 데이터 속성: `publicationDate`, `headlineText`
- 바뀌지 않는 기본 IRI: `https://example.com/ontology/press-release/`
- 온톨로지 IRI(ontology IRI)와 버전 IRI(version IRI) 분리

팀마다 이름 짓는 규칙이 다르면 매핑과 검색이 어려워진다. 처음부터 한 가지 규칙을 정해 지켜야 한다.

자주 쓰는 관례는 아래와 같다.

- 클래스는 대문자로, 속성은 소문자로 시작한다
- 여러 낱말을 이을 때 CamelCase와 밑줄 가운데 하나를 골라 끝까지 지킨다
- 클래스 이름은 단수와 복수 가운데 하나로 통일한다. 섞이면 `Wine`의 하위에 `Wines`를 또 만드는 일이 생긴다
- 속성 접두사는 `has-`와 `-of` 가운데 하나로 통일한다
- 이름에 `Class`·`Property` 같은 메타 낱말을 넣지 않고, 약어를 피한다

**이 관례는 포털의 공식 권고가 아니다.** 포털에 `Category:NamingOP`와 `Category:AnnotationOP` 분류는 있지만 **양쪽 모두 등재된 패턴이 없다.** Presentation ODP 계열 전체가 비어 있다. 위 관례는 널리 쓰이는 온톨로지 공학 관례이고, 출처는 Noy와 McGuinness의 `Ontology Development 101`이다.

Reasoning ODP와 함께, **표준 목록이 답을 주지 않는 자리**로 보아야 한다. 팀이 규칙을 정하고 문서로 남기는 수밖에 없다.

### 6.2 주석 패턴

사람과 도구가 온톨로지를 이해할 수 있도록 설명 메타데이터를 붙이는 패턴이다(Annotation ODP).

주로 아래 항목을 붙인다.

- `rdfs:label`
- `rdfs:comment`
- 개념 정의와 사용 예
- 한국어·영어 다국어 라벨
- 작성자와 출처
- 라이선스
- 버전과 변경 이력
- 폐기 여부와 대체 용어

주석은 대부분 OWL 추론 결과에 직접 영향을 주지 않는다. 그러나 검색·문서화와 LLM으로 온톨로지를 찾는 일에서는 매우 중요한 데이터가 된다.

---

## 7. 어휘·통사 패턴

자연어에서 되풀이되는 문장 구조를 논리 패턴이나 콘텐츠 패턴에 잇는다(Lexico-Syntactic ODP).

| 자연어 표현 | 뽑아낼 수 있는 온톨로지 구조 |
|---|---|
| “모든 X는 Y이다” | `X rdfs:subClassOf Y` 후보 |
| “X는 Y의 일부이다” | PartOf 또는 Componency 후보 |
| “X가 사건 Y에 참여했다” | Participation 후보 |
| “X는 A 또는 B이다” | 클래스 합집합 또는 완전 분할 후보 |
| “X의 P 값은 V이다” | 데이터 속성 또는 객체 속성 후보 |
| “X와 Y는 서로 다른 종류이다” | Disjoint Classes 후보 |

이 패턴은 문서에서 온톨로지 후보를 자동으로 뽑거나, 전문가의 요구사항을 모델로 옮길 때 쓴다. 다만 자연어는 모호하므로, 뽑아낸 결과를 바로 확정된 공리로 쓰면 안 된다.

예를 들어 “엔진은 자동차의 일부다”라는 문장만으로는 아래 셋 가운데 무엇인지 가리기 어렵다.

- 일반 `partOf`인가
- 직접 구성요소인 `componentOf`인가
- 특정 기간에만 장착된 시간 의존 관계인가

Lexico-Syntactic ODP는 후보 구조를 찾아내는 도구다. 최종 의미는 도메인 검토를 거쳐 정한다.

---

## 8. eXtreme Design

패턴 목록을 아는 것과 패턴을 쓰는 것은 다른 일이다. eXtreme Design(XD)은 **어떤 패턴을 언제 고르고 어떻게 넣을지**를 정한 방법론이다. 이름과 방식은 eXtreme Programming에서 왔다. 점진적 개발, 2인 1조 작업, 테스트 주도, 리팩터링, 분할 정복을 그대로 가져왔다.

### 8.1 문제 공간과 해 공간을 맞댄다

XD의 핵심은 두 공간을 맞대는 것이다.

| 공간 | 뜻 |
|---|---|
| 문제 공간(Local Use Case) | 지금 이 프로젝트에서 마주친 모델링 문제 |
| 해 공간(Generic Use Case) | 각 패턴이 “이럴 때 쓰라”고 밝혀 둔 적용 상황 |

패턴을 이름으로 고르지 않고, **적용 상황이 맞는지로 고른다.** 그래서 패턴 문서에는 의도와 역량 질문이 적혀 있어야 한다. 그것이 없는 패턴은 애초에 고를 수가 없다.

### 8.2 반복 주기

착수 단계에서는 범위와 쓸 패턴 목록을 정하고, 우선순위를 매긴 요구사항 목록을 만든다. 그다음부터는 2인 1조가 아래를 되풀이한다.

1. 아직 다루지 않은 요구사항 가운데 우선순위가 가장 높은 것 하나를 고른다
2. 그 요구사항을 **역량 질문 · 맥락 진술문 · 추론 요구사항**으로 쪼갠다. 맥락 진술문은 그 도메인에서 늘 성립해야 하는 일반 공리다
3. 서로 얽힌 역량 질문 하나 또는 몇 개를 묶어 이번 회차의 범위로 삼는다
4. 문제 공간과 해 공간을 맞대어 후보 패턴을 찾는다. 후보가 여럿이면 각각을 썼을 때 따라오는 결과를 근거로 고른다
5. 고른 패턴을 모듈에 넣는다
6. 모듈이 그 요구사항을 실제로 만족하는지 시험한다. 만족하지 못하면 2로 돌아간다
7. 요구사항이 남았으면 1로 돌아간다. 다 끝났으면 다른 조가 만든 모듈과 합쳐 평가하고 고친다

### 8.3 역량 질문이 곧 시험이다

XD에서 역량 질문은 설계를 시작하는 재료이면서 **검사 기준**이다. 역량 질문은 자연어로 써도 된다. 6번 “시험한다” 단계에서 실제로 하는 일은 그 질문을 질의문으로 바꿔 돌려 보는 것이다. 질의가 답을 내놓지 못하면 그 모듈은 아직 그 질문에 답하지 못하는 것이다.

구조를 눈으로 훑고 “답할 수 있어 보인다”고 판정하지 않는다는 점이 이 방법론의 요지다.

---

## 9. 안티패턴

패턴이 “이렇게 하라”라면 안티패턴은 **되풀이해서 나타나는 잘못된 모양**이다. 안티패턴마다 이름과 증상이 정해져 있어서, 이름을 알면 검토할 때 짚어 낼 수 있다.

안티패턴 목록은 세 갈래로 나뉜다. [Roussey · Corcho · Vilches-Blázquez (2009)](https://oa.upm.es/5142/1/kcap2009_submission_103.pdf), [Corcho 외 (2010)](https://oa.upm.es/6905/2/INVE_MEM_2010_75404.pdf)

| 갈래 | 뜻 |
|---|---|
| 검출 가능한 논리 안티패턴(DLAP) | 추론기가 모순으로 잡아낸다 |
| 인지적 논리 안티패턴(CLAP) | 추론기는 통과시키지만 모델링 의도와 어긋난다. 표현의 논리적 함의를 오해해서 생긴다 |
| 지침(Guidelines) | 논리상 틀리지 않았지만 더 단순한 표현이 있다 |

가운데 갈래가 가장 위험하다. **오류가 나지 않으므로 아무도 모르고 지나간다.**

### 9.1 검출 가능한 논리 안티패턴

| 이름 | 모양 | 착각한 내용 |
|---|---|---|
| AndIsOr (AIO) | `C1 ⊆ ∃R.(C2 ∩ C3)`인데 `C2`와 `C3`가 서로 배타 | 일상어의 “그리고”를 교집합으로 옮겼다. “A와 B를 다룬다”는 대개 합집합이다 |
| OnlynessIsLoneliness (OIL) | `C1 ⊆ ∀R.C2`와 `C1 ⊆ ∀R.C3`가 함께 있고 둘이 배타 | “오직 C2에만 이어진다”를 선언해 둔 것을 잊고 “오직 C3에만”을 또 선언했다 |
| UniversalExistence (UE) | `C1 ⊆ ∀R.C2`와 `C1 ⊆ ∃R.C3`가 함께 있고 둘이 배타 | 앞의 전역 제약을 잊고 어긋나는 존재 제약을 더했다 |
| EquivalenceIsDifference (EID) | `C1 ≡ C2`인데 둘이 배타로도 선언되어 있다 | “C1은 C2의 한 가지다”를 말하려다 동등으로 적었다 |

### 9.2 인지적 논리 안티패턴

| 이름 | 모양 | 착각한 내용 |
|---|---|---|
| SynonymOrEquivalence (SOE) | `C1 ≡ C2` | 같은 대상을 부르는 말이 둘이라는 뜻인데 논리적 동등으로 적었다. 이름이 둘인 것은 별칭으로 다룰 일이다 |
| SumOfSome (SOS) | `C1 ⊆ ∃R.C2`와 `C1 ⊆ ∃R.C3`가 함께 있고 둘이 배타 | 존재 제약을 이미 걸어 둔 것을 잊고 또 걸었다. 다만 늘 오류는 아니다. 자녀에게 어머니와 아버지가 각각 적어도 한 명씩 있는 경우처럼 정당한 쓰임도 있다 |
| SomeMeansAtLeastOne (SMALO) | `C1 ⊆ ∃R.C2`와 `C1 ⊆ (≥1 R.⊤)` | 존재 제약이 이미 “하나 이상”을 뜻하므로 개수 제약은 군더더기다 |

### 9.3 지침

| 이름 | 모양 | 짚는 내용 |
|---|---|---|
| DisjointnessOfComplement (DOC) | `C1 ≡ ¬C2` | “공유하는 개체가 없다”를 말하려면 여집합과의 동등보다 배타 선언이 낫다 |
| Domain & Cardinality Constraints (DCC) | `C1 ⊆ ∃R.C2`와 `C1 ⊆ (=2 R.⊤)` | “only”가 “some”을 함의하지 않는다는 점을 오해해 존재 제약과 개수 제약을 섞었다 |
| GroupAxioms (GA) | 같은 속성에 거는 제약이 흩어져 있다 | 하나로 묶어 적는다 |
| MinIsZero (MIZ) | `C1 ⊆ (≥0 R.⊤)` | 최소 0은 아무것도 제한하지 않는다. 지운다 |

**이 목록은 OWL의 논리 구성요소를 전제한다.** 배타 선언·전역 제약·개수 제약이 없는 표현 방식에서는 위 열한 가지 가운데 대부분이 성립하지 않는다. 그런 곳에서는 이 목록에서 안티패턴을 찾지 말아야 한다. 대신 쓰는 표현 방식에서 오류 없이 의도와 어긋나는 자리가 어디인지 따로 정리해야 한다.

“역할을 하위 클래스로 만든다”, “클래스와 개체를 혼동한다”, “계산 결과를 속성으로 둔다”처럼 흔히 안티패턴이라 불리는 것은 **위 목록에 없다**. ODP 쪽 문헌에서는 확인하지 못했고 다른 문헌에 있을 수 있으므로, 확인이 필요한 항목으로 남긴다.

### 9.4 포털에서 논리 패턴으로 등재된 안티패턴

포털에 OIL · SOE · DOC 세 가지가 **패턴 제출물로 등재되어 있고, 분류는 `Category:LogicalOP`이다.** 안티패턴 전용 분류(`Category:AntiPattern`)는 비어 있다.

읽을 때 조심해야 한다. 논리 패턴 목록을 훑다가 이 셋을 권장 패턴으로 집으면, 하지 말라는 것을 하게 된다. 각 페이지의 본문을 열어 「하지 말라」는 것인지 「하라」는 것인지 확인해야 한다.

---

## 10. 계열별 쓰임

여섯 계열은 하나만 고르는 대안이 아니다. 개발 단계마다 함께 쓴다.

| 개발 단계 | 적용할 ODP |
|---|---|
| 자연어 요구사항과 문서 분석 | Lexico-Syntactic |
| 기존 DB·UML·분류체계 변환 | Reengineering |
| 역할·사건·문서·시간 모델링 | Content |
| N항 관계와 OWL 제약 표현 | Logical |
| 모듈과 `owl:imports` 구조 결정 | Architectural |
| 원하는 자동 분류·추론 정의 | Reasoning |
| 외부 표준 온톨로지 연결 | Mapping/Alignment |
| 이름·설명·버전 정책 적용 | Presentation |

이 스킬의 흐름 단계마다 계열을 쓰는 법은 아래와 같다.

- Graphio에는 `owl:imports`·하위 클래스·공리·추론기가 없어 패턴을 그대로 들이지 못한다. 패턴의 꼴을 업무 이름으로 복제하는 방식만 쓴다
- 원문의 'all and only' 원칙(CQ 전부에 답하는 데 필요한 개념화를 빠짐없이, 그것만)에 원천 조건을 더해 '원천 근거가 있는 것만'으로 좁힌다. 좁혀서 빠지는 요소가 응답 불가 CQ 보고 대상이다

| 계열 | 흐름 단계 | 쓰는 법 | 원천 조건 |
|---|---|---|---|
| 어휘·통사(Lexico-Syntactic) | ② 값 모으기 | 문장 꼴로 조건 값·답 값·잇는 값을 가름. 'X와 Y'가 동시 조건인지 둘 중 하나인지 적음(AndIsOr 안티패턴의 Graphio판). 'X는 A 또는 B'는 코드 속성 저장값 후보 | 문장에서 뽑은 후보는 ②-1을 지나야 구조가 됨 |
| 대응: 재공학(Reengineering) | ②-1 원천 대조 | 테이블 → 대상, 외래 키 → 잇는 값, 분류코드 테이블 → 코드 개념 대응을 거꾸로 써서 CQ 요소마다 근거 꼴을 찾음. 원천을 출발점으로 쓰지 않음 | 원천 문서가 글자로 적은 것만 |
| 대응: 매핑(Mapping) | ②-2·⑥ 매핑 테이블 | 두 구조를 고치지 않고 대응만 선언하는 연결용 구조를 매핑 테이블로 구현([`source-match.md`](source-match.md) 4장). 이름 유사도로 대응하지 않음 | 기존 값만으로 행을 만듦 |
| 대응: 리팩터링(Refactoring) | 수정 단계 | 관계에 시점·수량·역할이 붙어야 하면 가운데 개념으로 다시 짬 | 딸린 값 컬럼을 가진 잇는 테이블이 원천에 있어야 함. 없으면 원천 부재로 보고 |
| 콘텐츠(Content) | ③~⑤ | CQ 꼴로 구조 꼴([`structure-patterns.md`](structure-patterns.md) 3.1)을 고르고 업무 이름으로 복제. 원문의 일반 사용 사례(GUC) 맞춰 보기 네 경우를 [`structure-patterns.md`](structure-patterns.md) 2장으로 옮김 | 꼴마다 원천 요구가 다름. 맞지 않으면 그 꼴은 쓰지 않음 |
| 구조: 논리(Logical) | ⑤ | N항 관계·관계 객체화를 가운데 개념으로 풂([`intermediate-concepts.md`](intermediate-concepts.md) 네 축). Graphio 제약(관계 속성 없음, GOS61106 자기 참조 금지)을 상위 식별 속성·가운데 개념으로 우회. 배타·전칭 제약은 경고문·설명으로 | 잇는 테이블이 원천에 있어야 가운데 개념을 둠 |
| 구조: 아키텍처(Architectural) | 해당 단계 없음(뼈대 관계를 고르는 멈춤은 다음 판본 몫) | 뼈대·가지 구분. 구조 꼴 사슬과 지나는 CQ 수·최대 홉 수를 핵심 축 후보 재료로 넘김 | 뼈대 관계마다 연결 키가 실제로 있어야 함 |
| 추론(Reasoning) | ⑨ CQ 판정(질의 계획) | 판정·집계·'마지막'은 속성이 아니라 질의가 함. 설계 리포트 4.1절 응답 경로에 질의 조건으로 적음. Materialization은 키 결합 매핑 테이블과 같은 꼴이나 기본 제안하지 않음 | 키 결합표를 만들려면 경로의 모든 키가 원천에 있어야 함 |
| 표현(Presentation) | ④·⑧ | 스타일 가이드의 이름·설명 규칙(이미 있음)을 그대로 씀 | 이름에 원천 컬럼명을 쓰지 않음(스타일 가이드 R-01), [SQL]에는 실제 테이블·컬럼만(스타일 가이드 R-03) |
| 안티패턴 | ⑨ 검사 | ODP 안티패턴 열한 가지는 OWL 구성요소를 전제해 Graphio에서는 대부분 성립하지 않음. 오류 없이 의도와 어긋나는 Graphio 꼴을 규칙으로 둠([`structure-patterns.md`](structure-patterns.md) 5장) | 정의 문서만으로 스크립트가 판정 |

---

## 11. 출처와 확인 범위

어디까지 원문으로 확인했는지 적어 둔다. 확인하지 못한 내용을 그대로 믿고 적용하면, 틀렸을 때 어디서 틀렸는지 되짚을 수 없다.

| 내용 | 확인한 곳 |
|---|---|
| 여섯 계열 분류 | 포털 `index.php/OPTypes` 원문 |
| 콘텐츠 패턴의 역량 질문·의도·한계 | 포털의 패턴 개별 페이지 원문(`Submissions:<이름>`) |
| 계열별 등재 목록과 개수 | 포털 `Category:<계열>OP` 원문 |
| Reasoning 계열과 Naming·Annotation 하위 유형이 비어 있다는 것 | 같은 분류 페이지에 등재 항목이 없음을 확인 |
| 안티패턴 정의와 세 갈래 | Roussey 외(2009) 원문, Corcho 외(2010) 원문. 포털 등재 사실은 `Category:LogicalOP`로 확인 |
| N항 관계 · Class as Property Value · Value Partition | W3C Working Group Note 세 편 원문 |
| eXtreme Design · 패턴 재사용 방식 | Hammar(2017) 2장·5장 |

확인하지 못한 것은 아래와 같다.

- **Rector(2003) Normalisation 원문.** DOI `10.1145/945645.945664`로 서지만 확인했다. 본문의 설명은 포털 등재 항목에서 가져왔다
- **Gangemi(2005) 원문.** ODP라는 말을 처음 제안한 문헌 가운데 하나인데 유료다
- **Defeasible · Qualified cardinality**를 독립 패턴으로 등재한 항목. 포털 논리 패턴 목록에 없다
- `Price` · `BasicPlan` · `CountingAs` · `DescriptionAndSituation` · `InformationObjectsAndRepresentationLanguages` · `TimeIndexedClassification`의 의도와 역량 질문. **페이지는 있지만 해당 칸이 비어 있다**

포털을 직접 열 때 주의할 점은 둘이다. **`https://`가 아니라 `http://`로 연다.** 그리고 **목록 페이지의 개수가 0으로 나와도 패턴이 없는 것이 아니다.** 개수를 세는 질의가 동작하지 않을 뿐, 패턴 페이지는 열린다.

주요 참고 문헌은 아래와 같다.

- [OntologyDesignPatterns.org 포털](http://ontologydesignpatterns.org/index.php/Main_Page) — ODPA 운영, NeOn 프로젝트에서 시작
- Hammar, K. (2017). *Content Ontology Design Patterns: Qualities, Methods, and Tools*. Linköping University. [전문](http://liu.diva-portal.org/smash/get/diva2:1131672/FULLTEXT02)
- Roussey, C., Corcho, O., Vilches-Blázquez, L.M. (2009). *A Catalogue of OWL Ontology AntiPatterns*. K-CAP. [전문](https://oa.upm.es/5142/1/kcap2009_submission_103.pdf)
- Corcho, O., Roussey, C., Šváb-Zamazal, O., Scharffe, F. (2010). *SPARQL-based Detection of Antipatterns in OWL Ontologies*. EKAW. [전문](https://oa.upm.es/6905/2/INVE_MEM_2010_75404.pdf)
- W3C. [Defining N-ary Relations](https://www.w3.org/TR/swbp-n-aryRelations/) · [Representing Classes As Property Values](https://www.w3.org/TR/swbp-classes-as-values/) · [Representing Specified Values](https://www.w3.org/TR/swbp-specified-values/)
- [ODPA 패턴 저장소](https://github.com/odpa/patterns-repository) — 포털 내용을 옮겨 둔 곳
