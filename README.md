# supersohee.com Backend (농구선수 팬페이지)

이 프로젝트는 **supersohee.com**의 백엔드로, Python Flask를 사용하여 웹 크롤링을 수행하고, 크롤링된 데이터를 기반으로 API를 제공하는 시스템도 가지고 있습니다. 
특정 농구 관련 사이트에서 이소희 선수 관련 기사를 정기적으로 크롤링하여 팬들이 최신 정보를 쉽게 확인할 수 있도록 합니다.
그외에도 방명록, 직관일지 등 MongoDB 데이터베이스를 연결하여 저장하고 읽어야 하는 데이터들의 api를 작성하여 프론트엔드에 제공하고 있습니다. 

## 주요 기능
- **웹 크롤링**: 점프볼(Jumpball)과 루키(Rookie)에서 이소희 선수 관련 기사 크롤링
- **REST API 제공**: 크롤링된 데이터를 API로 제공하여, 프론트엔드에서 사용할 수 있게 함
- **Blueprint 사용**: Flask의 Blueprint를 사용하여 API와 각 기능을 모듈화하여 관리, 코드 가독성 및 유지보수성 향상
- **크롤링 자동화**: 일정 주기로 크롤링을 수행하여 최신 데이터를 유지
- **에러 핸들링**: 크롤링 중 발생할 수 있는 예외 상황을 처리하여 서버 안정성 유지
- **직관일지 통계 데이터 제공**: 직관일지를 통해 받은 날씨, 승패여부, 홈경기 여부 등의 데이터를 받아 1시즌 기준 160경기 대비 얼마의 직관률과 승률을 가지고 있는지, 홈경기 승률은 어떤지 등등의 개인 데이터를 제공하고 있음. 

## 사용된 기술 스택
- **백엔드 프레임워크**: Flask
- **웹 크롤링**: BeautifulSoup, Requests
- **데이터베이스**: MongoDB와 GridFS를 함께 사용하여 데이터와 대용량 파일(이미지)을 저장. MongoDB는 직관일지와 같은 텍스트 데이터 관리에 사용되며, GridFS는 이미지 파일을 저장하고 관리하는 데 사용됨.
- **배포**: CloudType (또는 사용된 배포 방식)
- **API 관리**: Flask-RESTful

## 기술 사용이유 
- Flask : 크롤링에 최적화된 프레임워크라고 생각했고, 통계데이터를 뽑아내기도 좋아서 사용했습니다. Blueprint 기능으로 코드 가독성도 좋아졌습니다.

## 트러블 슈팅 
1. 강제 크롤링 이슈
- 문제: 크롤링이 특정 상황에서 강제로 실행되어 중복된 데이터를 가져오는 문제가 발생.
- 원인: 크롤링을 트리거하는 조건이 제대로 설정되지 않아 강제로 크롤링이 반복됨.
- 해결 방법: 크롤링 조건을 다시 설정하고, 이미 크롤링된 데이터가 있을 경우 새로 요청하지 않도록 캐싱 및 상태 관리를 개선.


2. 이미지 전송 이슈
- 이미지 저장 방식 : 폼데이터로 받았지만, 이미지는 별도의 폴더에서 관리하고 ID 값을 부여하여 추후 호출되었을때 같은 ID값을 가진 이미지를 찾아서 가져오는 방식.
- 문제: 이미지 전송 중 발생한 문제로 인해, 이미지가 제대로 전달되지 않거나 파일 전송 속도가 느려짐.
- 해결 방법: 이미지를 Base64 형식으로 변환하여 프론트엔드로 전송함으로써 전송 시의 문제를 해결. Base64로 변환된 이미지 데이터를 프론트엔드에서 다시 디코딩하여 표시.


## 코드 구조
Flask의 Blueprint를 사용하여 애플리케이션의 각 기능을 모듈화하여 관리하고 있습니다. 이를 통해 코드 가독성과 유지보수성을 높였으며, 각 기능을 독립적으로 관리할 수 있습니다.

- **app/**: Flask 애플리케이션의 메인 디렉토리
  - **auth_routes.py**: 사용자 인증 관련 API를 관리하는 Blueprint (`auth_bp`)
  - **user_routes.py**: 사용자 관리와 관련된 API를 정의한 Blueprint (`user_bp`)
  - **guestbook_routes.py**: 방명록 작성 및 조회 기능을 위한 Blueprint (`guestbook_bp`)
  - **event_routes.py**: 이벤트 활동 기록을 위한 API를 관리하는 Blueprint (`event_bp`)
  - **admin.py**: 관리자 기능을 처리하는 Blueprint (`admin_bp`)
  - **photo_routes.py**: 사진 업로드 및 조회와 관련된 기능을 위한 Blueprint (`photo_bp`)
  - **schedule_routes.py**: 경기 일정 확인 및 관리 API를 위한 Blueprint (`schedule_bp`)
  - **stats_routes.py**: 통계 데이터를 처리하는 API를 정의한 Blueprint (`stats_bp`)
  - **newsrookie_routes.py**: 루키(Rookie) 사이트에서 기사를 크롤링하는 API를 담당하는 Blueprint (`newsrookie_bp`)
  - **newsjump_routes.py**: 점프볼(Jumpball) 사이트에서 기사를 크롤링하는 API를 담당하는 Blueprint (`newsjumpball_bp`)
  - **news_routes.py**: 뉴스 데이터를 통합하여 처리하는 API를 위한 Blueprint (`news_bp`)
  - **diary_routes.py**: 직관일지(경기 일지) 데이터를 관리하는 API를 정의한 Blueprint (`diary_bp`)

- **app.py**: Flask 애플리케이션의 엔트리포인트로, 위의 Blueprint들을 모두 등록하여 API 라우트를 설정합니다.


### 참고사항

프론트엔드 깃허브
[:link:](https://github.com/superrookie8/sofanpage)

## 배포된 사이트
[supersohee.com](https://www.supersohee.com)

