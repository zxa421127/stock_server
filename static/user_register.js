(() => {
  "use strict";
  const image = document.getElementById("registration-captcha");
  if (!image) return;
  image.addEventListener("click", () => {
    image.src = `/user/register/captcha.png?t=${Date.now()}`;
  });
})();
