(() => {
  "use strict";
  const image = document.getElementById("adminCaptchaImage");
  const button = document.getElementById("refreshAdminCaptcha");
  const input = document.querySelector('input[name="captcha"]');
  if (!image) return;
  const refresh = () => {
    image.src = `/admin/captcha.png?t=${Date.now()}`;
    if (input) {
      input.value = "";
      input.focus();
    }
  };
  image.addEventListener("click", refresh);
  if (button) button.addEventListener("click", refresh);
  image.addEventListener("error", () => {
    image.alt = "验证码加载失败，请刷新页面";
  });
})();
