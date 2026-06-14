chrome.storage.local.get("oces_profile", function (data) {
  var p = data.oces_profile || {};
  var el = document.getElementById("summary");
  if (p.title) {
    el.textContent = "저장됨: " + p.title + (p.author ? " / " + p.author : "");
  } else {
    el.textContent = "기본정보가 없습니다. '기본정보 편집'에서 한 번 입력하세요.";
  }
});

document.getElementById("fill").addEventListener("click", function () {
  chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
    if (!tabs[0]) return;
    chrome.tabs.sendMessage(tabs[0].id, { type: "OCES_FILL" }, function (resp) {
      var el = document.getElementById("summary");
      if (chrome.runtime.lastError || !resp) {
        el.textContent = "이 페이지에서 실행할 수 없습니다(새로고침 후 시도).";
        return;
      }
      el.textContent = "채움 " + resp.filled.length + "칸 · 첨부필요 " + resp.manual.length + "칸";
    });
  });
});

document.getElementById("opts").addEventListener("click", function () {
  chrome.runtime.openOptionsPage();
});
