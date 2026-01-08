#!/bin/bash
# Manual API Test Script for StoLink Chat Service
# Usage: ./tests/manual_test.sh
#
# 테스트 항목:
# 1. Health Check
# 2. Neo4j 청크 저장 (/ai-api/editor/save)
# 3. PostgreSQL 문장 임베딩 저장 (직접 SQL)
# 4. Hybrid Search 챗봇 테스트 (/ai-api/chat/stream)

BASE_URL="${BASE_URL:-http://localhost:8000}"
PROJECT_ID="novel-test-001"
USER_ID="test-user-001"
SESSION_ID="test-session-$(date +%s)"

# 색상 출력
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== StoLink Chat Service Manual Test ===${NC}"
echo "Base URL: $BASE_URL"
echo "Project ID: $PROJECT_ID"
echo ""

# 1. Health Check
echo -e "${YELLOW}1. Health Check${NC}"
health=$(curl -s "$BASE_URL/health")
if echo "$health" | grep -q "healthy"; then
  echo -e "${GREEN}✓ Service is healthy${NC}"
else
  echo -e "${RED}✗ Service is not running${NC}"
  exit 1
fi
echo ""

# 2. Save Editor Chunks (Neo4j)
echo -e "${YELLOW}2. Saving Editor Chunks to Neo4j...${NC}"

declare -a chunks=(
  # === 1장: 시작 ===
  'chunk-ch1-001|1장. 시작

서울의 어느 허름한 아파트. 김민준은 창밖을 바라보며 한숨을 쉬었다. 스물다섯, 대학을 졸업한 지 2년이 지났지만 아직 제대로 된 직장을 구하지 못했다. 컴퓨터 공학을 전공했지만, 수백 번의 이력서와 면접 끝에 그가 얻은 것은 무력감뿐이었다.'

  'chunk-ch1-002|민준의 방은 좁았다. 침대 하나, 책상 하나, 그리고 낡은 노트북이 전부였다. 벽에는 대학 시절 해커톤에서 받은 상장이 걸려 있었다. AI 기반 보안 시스템으로 1등을 했던 그때가 인생의 정점이었다. 지금은 그 상장조차 빛바랜 추억일 뿐이었다.'

  'chunk-ch1-003|그의 유일한 친구 박서연은 대기업 네오텍에 취직해 바쁜 나날을 보내고 있었다. 고등학교 때부터 절친이었던 두 사람은 이제 한 달에 한 번 만나기도 힘들었다. 서연이는 항상 민준에게 희망을 잃지 말라고 했지만, 말처럼 쉬운 일이 아니었다.'

  'chunk-ch1-004|서연은 키가 크고 단정한 외모의 여성이었다. 긴 생머리에 항상 깔끔한 정장을 입고 다녔다. 네오텍의 AI 연구팀에서 일하며 승승장구하고 있었다. 그녀는 민준의 재능을 누구보다 잘 알았기에, 그가 이렇게 무너져가는 모습이 안타까웠다.'

  'chunk-ch1-005|어느 날 저녁, 민준은 편의점에서 라면을 사 들고 집으로 돌아왔다. 현관문을 열자 어둠 속에서 노트북 화면만 희미하게 빛나고 있었다. 그런데 이상했다. 분명 끄고 나갔는데, 노트북이 켜져 있었다. 화면에는 새 이메일 알림이 떠 있었다.'

  # === 2장: 이상한 이메일 ===
  'chunk-ch2-001|2장. 이상한 이메일

어느 날 밤, 민준의 노트북에 이상한 이메일이 도착했다. 발신자는 X라는 익명이었고, 제목은 당신의 재능을 알아봤습니다였다. 평소라면 스팸으로 치부했겠지만, 이메일 본문에는 민준이 대학 시절 만들었던 프로젝트의 상세한 분석이 담겨 있었다.'

  'chunk-ch2-002|이메일에는 민준의 해커톤 프로젝트인 쉐도우가드에 대한 상세한 기술 분석이 담겨 있었다. 쉐도우가드는 AI가 실시간으로 네트워크 침입을 탐지하고 차단하는 보안 시스템이었다. 놀라운 것은, 이메일 발신자가 쉐도우가드의 숨겨진 백도어까지 발견했다는 점이었다. 그건 민준 자신도 잊고 있던 부분이었다.'

  'chunk-ch2-003|이메일의 마지막에는 주소가 적혀 있었다. 강남구 테헤란로에 위치한 넥서스 타워 지하 3층. 민준은 고민했다. 위험할 수도 있었다. 하지만 지금 상황에서 잃을 것도 없었다. 그는 다음 날 아침, 그 주소를 찾아가기로 결심했다.'

  'chunk-ch2-004|민준은 서연에게 메시지를 보냈다. 내일 강남에 갈 일이 있어. 혹시 뭔가 이상하면 연락해. 서연은 곧바로 답장을 보내왔다. 무슨 일인데? 위험한 거 아니지? 민준은 잠시 망설이다가 답했다. 아니야, 그냥 면접 비슷한 거야. 거짓말이었지만, 서연을 걱정시키고 싶지 않았다.'

  'chunk-ch2-005|밤새 잠을 이루지 못한 민준은 새벽에 일어나 넥서스 타워에 대해 검색했다. 공식적으로는 여러 IT 스타트업이 입주한 일반 오피스 빌딩이었다. 하지만 지하 3층에 대한 정보는 어디에도 없었다. 마치 그 층은 존재하지 않는 것처럼.'

  # === 3장: 신비로운 만남 ===
  'chunk-ch3-001|3장. 신비로운 만남

강남의 넥서스 타워 로비에 들어선 민준을 맞이한 것은 단정한 정장 차림의 여성이었다. 그녀는 자신을 이수아라고 소개했다. 나이는 민준과 비슷해 보였지만, 눈빛에는 형언할 수 없는 깊이가 있었다. 마치 수백 년을 살아온 사람 같았다.'

  'chunk-ch3-002|수아는 민준을 지하로 안내했다. 일반 엘리베이터가 아니었다. 로비 한쪽 벽에 숨겨진 비밀 통로를 통해 특수 엘리베이터로 이동했다. 엘리베이터 안에서 수아가 손목의 홀로그램 장치로 무언가를 입력하자, 엘리베이터가 움직이기 시작했다.'

  'chunk-ch3-003|지하 3층에 도착하자 거대한 연구 시설이 펼쳐졌다. 수십 명의 연구원들이 분주하게 움직이고 있었고, 벽면에는 알 수 없는 기호와 차트가 가득했다. 중앙에는 거대한 원형 구조물이 있었는데, 푸른 빛을 내뿜고 있었다. 리프트라고 불리는 장치였다.'

  'chunk-ch3-004|수아는 민준을 충격적인 사실을 알게 되었다. 이 세계에는 일반인들이 모르는 또 다른 차원이 존재했고, 그 차원의 균열을 막는 비밀 조직이 있었다. 그 조직의 이름은 넥서스. 그리고 민준의 코딩 능력은 그 균열을 제어하는 핵심 기술이 될 수 있다는 것이었다.'

  'chunk-ch3-005|다른 차원은 보이드라고 불렸다. 보이드는 우리 세계와 평행하게 존재하는 어둠의 차원이었다. 가끔 두 차원 사이에 균열이 생기면, 보이드의 존재들이 우리 세계로 넘어왔다. 넥서스는 50년 전부터 이 균열을 감시하고 봉인해왔다.'

  # === 4장: 첫 번째 임무 ===
  'chunk-ch4-001|4장. 첫 번째 임무

민준은 넥서스에 합류하기로 결심했다. 다른 선택지가 있었을까? 세계의 비밀을 알아버린 이상, 평범하게 살 수는 없었다. 수아는 민준에게 첫 번째 임무를 맡겼다. 홍대 근처에서 감지된 작은 균열을 봉인하는 것이었다.'

  'chunk-ch4-002|민준은 새로운 장비를 받았다. 손목에 차는 홀로그램 인터페이스 오라클, 균열을 감지하는 스캐너, 그리고 보이드 생명체를 무력화할 수 있는 나노 필드 발생기. 모두 일반인의 눈에는 보이지 않도록 설계되어 있었다.'

  'chunk-ch4-003|홍대의 어느 골목. 민준은 스캐너를 통해 균열의 위치를 확인했다. 작은 크랙이 공중에 떠 있었고, 그 틈에서 검은 안개가 새어나오고 있었다. 오라클이 경고음을 울렸다. 보이드 에너지 감지. 레벨 2. 즉시 봉인 권장.'

  'chunk-ch4-004|민준은 처음으로 봉인 코드를 입력했다. 그의 머릿속에서 코드가 자동으로 생성되었다. 마치 평생 해왔던 것처럼 자연스러웠다. 화면에 코드가 흐르고, 균열이 서서히 닫히기 시작했다. 성공이었다. 하지만 그 순간, 균열에서 무언가가 튀어나왔다.'

  'chunk-ch4-005|그것은 그림자 같은 형체였다. 사람의 형상이었지만 얼굴이 없었다. 쉐이드라고 불리는 저급 보이드 생명체였다. 민준은 당황했지만, 본능적으로 나노 필드 발생기를 작동시켰다. 푸른 빛이 쉐이드를 감싸고, 그것은 비명 같은 소리를 내며 사라졌다.'

  # === 5장: 팀원들 ===
  'chunk-ch5-001|5장. 팀원들

첫 임무를 성공적으로 마친 민준은 정식 팀에 배정되었다. 알파 팀. 넥서스에서 가장 경험이 풍부한 현장 요원들로 구성된 팀이었다. 팀장은 40대 초반의 남성, 강동현이었다. 과묵하지만 카리스마 있는 인물이었다.'

  'chunk-ch5-002|알파 팀에는 세 명의 멤버가 더 있었다. 의료 담당 한유진, 정보 분석가 최재혁, 그리고 전투 전문가 김하늘. 유진은 온화한 성격의 30대 여성으로, 보이드 에너지로 인한 부상을 치료할 수 있는 특수 능력이 있었다.'

  'chunk-ch5-003|재혁은 안경을 쓴 마른 체형의 남성이었다. 해킹과 정보 수집의 천재였다. 민준과 비슷한 배경을 가지고 있었지만, 그는 넥서스에서 10년을 근무한 베테랑이었다. 민준에게 여러 가지를 가르쳐주겠다고 했다.'

  'chunk-ch5-004|하늘은 짧은 머리에 날카로운 눈매를 가진 여성이었다. 특수부대 출신으로, 보이드 생명체와의 전투에서 누구보다 뛰어났다. 처음에는 민준을 신뢰하지 않았지만, 그의 능력을 인정한 후에는 든든한 동료가 되었다.'

  'chunk-ch5-005|동현 팀장이 민준에게 말했다. 이 팀에서 중요한 건 신뢰야. 우린 서로의 목숨을 맡기는 사이거든. 너도 곧 알게 될 거야. 보이드와 싸우는 건 혼자선 불가능해. 반드시 팀이 필요하지. 민준은 고개를 끄덕였다. 새로운 가족이 생긴 것 같았다.'

  # === 6장: 서연의 의심 ===
  'chunk-ch6-001|6장. 서연의 의심

민준의 생활은 완전히 바뀌었다. 낮에는 넥서스에서 훈련을 받고, 밤에는 균열 봉인 임무를 수행했다. 서연과 연락하는 횟수가 점점 줄어들었다. 서연은 민준의 변화를 눈치채기 시작했다.'

  'chunk-ch6-002|어느 날, 서연이 민준의 아파트를 방문했다. 문을 열자 서연은 깜짝 놀랐다. 민준의 방이 깨끗하게 정돈되어 있었고, 새 옷과 장비들이 보였다. 넌 대체 요즘 뭐 하는 거야? 돈은 어디서 나는 거고? 서연의 목소리에는 걱정이 가득했다.'

  'chunk-ch6-003|민준은 거짓말을 했다. 프리랜서 개발 일을 시작했어. 재택근무라 바쁘긴 한데, 수입은 괜찮아. 서연은 믿는 척했지만, 그녀의 눈빛은 의심으로 가득했다. 네오텍의 AI 연구원인 그녀는 거짓말을 쉽게 알아차렸다.'

  'chunk-ch6-004|서연은 몰래 민준을 미행하기 시작했다. 어느 날 밤, 민준이 홍대의 어두운 골목으로 들어가는 것을 봤다. 그리고 그곳에서 푸른 빛이 번쩍이는 것을 목격했다. 서연은 충격을 받았다. 민준이 대체 무슨 일에 연루된 걸까?'

  'chunk-ch6-005|다음 날, 서연은 민준에게 직접적으로 물었다. 네가 뭔가 숨기고 있는 거 알아. 제발 솔직하게 말해줘. 우리 친구잖아. 민준은 괴로웠다. 진실을 말하고 싶었지만, 넥서스의 규칙상 일반인에게는 비밀을 유지해야 했다.'

  # === 7장: 위기 ===
  'chunk-ch7-001|7장. 위기

서울 시내에서 대규모 균열이 감지되었다. 레벨 5. 지금까지 기록된 것 중 가장 큰 규모였다. 넥서스의 모든 팀이 비상 소집되었다. 알파 팀도 즉시 현장으로 출동했다. 위치는 여의도 IFC 몰 지하.'

  'chunk-ch7-002|현장에 도착했을 때, 이미 보이드 생명체들이 쏟아져 나오고 있었다. 쉐이드뿐만 아니라 더 강력한 헌터들도 있었다. 헌터는 거대한 늑대 형상의 생명체로, 쉐이드보다 훨씬 위험했다. 하늘이 앞장서서 전투를 시작했다.'

  'chunk-ch7-003|민준은 균열을 봉인하기 위해 오라클을 작동시켰다. 하지만 이번 균열은 너무 거대했다. 일반적인 봉인 코드로는 불가능했다. 재혁이 새로운 알고리즘을 민준에게 전송했다. 시험도 안 해본 코드야. 하지만 이게 유일한 방법이야.'

  'chunk-ch7-004|민준이 새 알고리즘을 실행하려는 순간, 균열에서 거대한 그림자가 나타났다. 아크메이지. 보이드의 고위 존재였다. 인간의 형상이었지만 몸 전체가 검은 안개로 이루어져 있었다. 오랜만이군, 인간들. 아크메이지가 으스스한 목소리로 말했다.'

  'chunk-ch7-005|아크메이지는 손짓 한 번으로 하늘과 동현을 날려버렸다. 유진이 부상자들에게 달려갔다. 재혁이 외쳤다. 민준! 봉인해! 지금 당장! 민준은 떨리는 손으로 코드를 입력했다. 균열이 닫히기 시작했지만, 아크메이지도 그것을 막으려 했다.'

  # === 8장: 숨겨진 힘 ===
  'chunk-ch8-001|8장. 숨겨진 힘

민준의 머릿속에서 무언가가 깨어났다. 갑자기 그의 시야가 바뀌었다. 균열의 구조가 완벽하게 보였다. 마치 프로그램의 소스 코드를 보는 것처럼. 그는 본능적으로 새로운 코드를 입력하기 시작했다. 아무도 가르쳐주지 않은 코드였다.'

  'chunk-ch8-002|오라클에서 경고음이 울렸다. 알 수 없는 코드 실행 중. 시스템 한계 초과. 하지만 민준은 멈추지 않았다. 그의 손가락이 빛의 속도로 움직였다. 아크메이지가 당황한 표정을 지었다. 너는... 무엇이냐?'

  'chunk-ch8-003|거대한 빛이 균열을 감쌌다. 아크메이지가 비명을 지르며 보이드로 밀려났다. 균열이 완전히 봉인되었다. 민준은 쓰러졌다. 눈앞이 어두워지며 의식을 잃었다. 마지막으로 들린 것은 팀원들의 걱정스러운 목소리였다.'

  'chunk-ch8-004|민준이 눈을 떴을 때, 그는 넥서스의 의료실에 있었다. 유진이 옆에서 그를 지켜보고 있었다. 깨어났구나. 다행이야. 민준은 자신의 손을 바라봤다. 희미하게 푸른 빛이 흐르고 있었다. 뭔가 변한 것 같았다.'

  'chunk-ch8-005|수아가 의료실로 들어왔다. 그녀의 표정은 진지했다. 민준, 네가 방금 한 것은... 보이드 언어야. 그건 인간이 쓸 수 있는 게 아니야. 넌 대체 누구니? 민준도 대답할 수 없었다. 자신도 모르는 힘이 자신 안에 있다는 것을 처음 알았기 때문이다.'

  # === 9장: 과거의 비밀 ===
  'chunk-ch9-001|9장. 과거의 비밀

수아는 민준을 넥서스의 기록 보관소로 데려갔다. 25년 전의 기록을 보여줬다. 프로젝트 제네시스. 인간과 보이드 에너지를 융합하려는 비밀 실험이었다. 대부분의 피험자가 사망했지만, 한 명의 영아가 살아남았다.'

  'chunk-ch9-002|그 영아는 입양되었다. 입양 부모의 이름은 김정수와 박미영. 민준의 부모님이었다. 민준은 충격을 받았다. 그러니까... 내가 그 실험의 결과물이라는 거야? 수아가 고개를 끄덕였다. 너의 특별한 능력은 그때부터 잠재되어 있었던 거야.'

  'chunk-ch9-003|민준의 친부모에 대한 기록은 삭제되어 있었다. 하지만 단서가 하나 있었다. 프로젝트 제네시스의 책임자였던 과학자, 이현우 박사. 그는 실험 실패 후 넥서스를 떠났고, 현재 행방은 알 수 없었다.'

  'chunk-ch9-004|민준은 자신의 과거를 알기 위해 이현우 박사를 찾기로 결심했다. 재혁이 정보를 추적했다. 이현우 박사는 현재 제주도에 은거하고 있었다. 가짜 신분으로 평범한 노인처럼 살고 있었다.'

  'chunk-ch9-005|민준은 제주도로 향했다. 혼자였다. 이것은 개인적인 일이었고, 팀을 위험에 빠뜨리고 싶지 않았다. 하지만 그는 몰랐다. 누군가가 그를 미행하고 있다는 것을. 그리고 그 누군가는 다름 아닌 서연이었다.'

  # === 10장: 진실 ===
  'chunk-ch10-001|10장. 진실

제주도의 작은 마을. 민준은 이현우 박사의 집을 찾았다. 낡은 한옥이었다. 문을 두드리자 백발의 노인이 나왔다. 민준을 보자 그의 얼굴이 굳어졌다. 드디어 왔군. 널 기다리고 있었다.'

  'chunk-ch10-002|이현우 박사는 모든 것을 털어놓았다. 프로젝트 제네시스는 보이드와의 전쟁에서 이기기 위한 필사적인 시도였다. 인간에게 보이드의 힘을 부여하려 했다. 하지만 대부분이 실패했다. 민준만이 성공 사례였다.'

  'chunk-ch10-003|너의 친부모는... 나였다. 이현우 박사가 말했다. 정확히는, 너의 친아버지가 나야. 민준은 할 말을 잃었다. 박사가 계속했다. 너의 어머니는 넥서스의 요원이었어. 실험 중에 사망했지. 나는... 너를 지킬 수가 없었어.'

  'chunk-ch10-004|그때 집 밖에서 소리가 들렸다. 서연이었다. 그녀는 민준과 박사의 대화를 엿듣고 있었다. 민준은 서연을 발견하고 충격을 받았다. 서연... 왜 여기에? 서연은 눈물을 흘리며 말했다. 네가 무슨 일에 연루됐는지 알고 싶었어. 근데 이게 대체...'

  'chunk-ch10-005|갑자기 하늘이 어두워졌다. 보이드의 기운이 느껴졌다. 이현우 박사의 얼굴이 창백해졌다. 그들이 찾아왔군. 민준, 어서 떠나야 해. 너의 친어머니를 죽인 자들이야. 그들은 아직도 널 찾고 있어.'
)

for chunk_data in "${chunks[@]}"; do
  IFS='|' read -r chunk_id content <<< "$chunk_data"
  echo -n "  Saving $chunk_id... "

  # JSON 이스케이프 처리
  escaped_content=$(echo "$content" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))')

  result=$(curl -s -X POST "$BASE_URL/ai-api/editor/save" \
    -H "Content-Type: application/json" \
    -d "{\"chunk_uuid\":\"$chunk_id\",\"content\":$escaped_content,\"project_id\":\"$PROJECT_ID\",\"user_id\":\"$USER_ID\"}")

  if echo "$result" | grep -q "accepted"; then
    echo -e "${GREEN}✓${NC}"
  else
    echo -e "${RED}✗${NC}"
    echo "  Error: $result"
  fi
done
echo ""

# 3. Wait for embedding processing
echo -e "${YELLOW}3. Waiting for embedding processing (simulated by external agent)...${NC}"
# In a real scenario, we would wait for the external agent to process the chunks and insert into Postgres.
# For this test, if we don't have the external agent running, the search test might return empty results unless we manually insert.
sleep 2
echo ""

# 4. Chat Stream Tests
echo -e "${YELLOW}4. Chat Stream Tests (PostgreSQL Search)${NC}"
echo ""

# 스트리밍 응답을 파싱하는 함수
parse_stream() {
  local first_source=true
  while IFS= read -r line; do
    if [[ $line == data:* ]]; then
      json="${line#data: }"

      # Python으로 JSON 파싱
      parsed=$(echo "$json" | python3 -c '
import sys, json
try:
    d = json.loads(sys.stdin.read())
    t = d.get("type", "")
    if t == "sources":
        sources = d.get("sources", [])
        if sources:
            print("SOURCES:" + str(len(sources)))
            for s in sources[:3]:
                src = s.get("source", "?")
                src_type = s.get("source_type", "?")
                score = s.get("score", 0)
                content = s.get("content", "")[:50]
                print(f"  [{src}:{src_type}] score={score:.3f} | {content}...")
        else:
            print("SOURCES:0")
    elif t == "token":
        print("TOKEN:" + d.get("content", ""), end="")
    elif t == "done":
        print("\nDONE")
    elif t == "error":
        print("ERROR:" + d.get("error", ""))
except:
    pass
' 2>/dev/null)

      if [[ $parsed == SOURCES:* ]]; then
        count="${parsed#SOURCES:}"
        if [[ $count == "0" ]]; then
          echo -e "  ${RED}[No sources found]${NC}"
        else
          echo -e "  ${GREEN}[Found $count sources]${NC}"
          # 소스 상세 출력
          echo "$json" | python3 -c '
import sys, json
d = json.loads(sys.stdin.read())
for s in d.get("sources", [])[:3]:
    src = s.get("source", "?")
    src_type = s.get("source_type", "?")
    score = s.get("score", 0)
    content = s.get("content", "")[:60].replace("\n", " ")
    print(f"    [{src}:{src_type}] {score:.3f} | {content}...")
' 2>/dev/null
        fi
      elif [[ $parsed == TOKEN:* ]]; then
        printf "%s" "${parsed#TOKEN:}"
      elif [[ $parsed == "DONE" ]]; then
        echo ""
      elif [[ $parsed == ERROR:* ]]; then
        echo -e "${RED}${parsed}${NC}"
      fi
    fi
  done
}

questions=(
  "주인공의 이름이 뭐야?"
  "서연이는 누구야? 민준이랑 무슨 관계야?"
  "민준이는 왜 그 빌딩을 찾아갔어?"
  "이수아는 민준에게 뭘 알려줬어?"
)

for question in "${questions[@]}"; do
  echo -e "${BLUE}Q: $question${NC}"
  echo -n "A: "

  curl -sN -X POST "$BASE_URL/ai-api/chat/stream" \
    -H "Content-Type: application/json" \
    -H "Accept: text/event-stream" \
    -d "{\"message\":\"$question\",\"project_id\":\"$PROJECT_ID\",\"user_id\":\"$USER_ID\",\"session_id\":\"$SESSION_ID\"}" \
    2>/dev/null | parse_stream

  echo ""
  echo "---"
  sleep 1
done

echo ""
echo -e "${BLUE}=== Test Complete ===${NC}"
echo ""
echo "Summary:"
echo "  - Project: $PROJECT_ID"
echo "  - Session: $SESSION_ID"
echo "  - Chunks saved to Neo4j: ${#chunks[@]}"
echo ""
echo "Tips:"
echo "  - Neo4j sources: source=neo4j, source_type=chunk"
echo "  - PostgreSQL sources: source=postgresql, source_type=sentence"
echo "  - Check logs: docker-compose logs fastapi --tail 50"
