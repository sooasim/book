@echo off
REM SYNC_LOCAL.bat — 더블클릭으로 GitHub 최신 내용을 E:\추가프로젝트\book 에 자동 반영
setlocal
set TARGET=E:\추가프로젝트\book
set REPO=https://github.com/sooasim/book.git
set BRANCH=claude/gallant-hopper-kGgs8

where git >nul 2>nul
if errorlevel 1 (
  echo [오류] git 이 필요합니다. https://git-scm.com 에서 설치 후 다시 실행하세요.
  pause & exit /b 1
)

if exist "%TARGET%\.git" (
  echo 기존 저장소 갱신: %TARGET%
  git -C "%TARGET%" fetch origin
  git -C "%TARGET%" checkout %BRANCH%
  git -C "%TARGET%" pull origin %BRANCH%
) else (
  echo 새로 클론: %REPO% -^> %TARGET%
  git clone -b %BRANCH% %REPO% "%TARGET%"
)

echo.
echo 최신 커밋:
git -C "%TARGET%" log --oneline -1
echo.
echo 동기화 완료: %TARGET%
echo 크롬 확장: chrome://extensions - 개발자 모드 - 압축해제된 확장 로드 - %TARGET%\apps\ebook_publisher\chrome_extension
pause
