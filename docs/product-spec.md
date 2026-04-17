# Scorecraft MVP

## Problem
영상이나 오디오를 참고해 빠르게 연습용 악보 초안을 만들고 싶지만, 완전 수작업 채보는 시간이 오래 걸립니다.

## Goal
- YouTube 링크 또는 오디오 파일 입력
- AI 기반 음표 추출
- MusicXML / MIDI / 코드 진행 출력
- 브라우저에서 악보 미리보기

## Target use cases
- 피아노 독주 연습용 초안
- 단선율 멜로디 채보
- 단순 반주곡의 코드 확인

## Core flow
1. 사용자가 링크 또는 파일 업로드
2. 서버가 오디오 추출/정규화
3. Basic Pitch로 MIDI 생성
4. music21로 MusicXML과 코드 분석
5. 웹에서 결과 렌더링 및 다운로드 제공

## Known limits
- 라이브 녹음, 오케스트라, 보컬+밴드 편성은 정확도가 낮을 수 있음
- 생성 결과는 초안이며 수동 보정이 필요함
