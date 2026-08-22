(function () {
  'use strict';

  function confirmationMessage(element) {
    return (element && element.getAttribute('data-confirm')) || '';
  }

  document.addEventListener('submit', function (event) {
    var message = confirmationMessage(event.target);
    if (message && !window.confirm(message)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  document.addEventListener('click', function (event) {
    var element = event.target.closest('[data-confirm]');
    if (!element || element.tagName === 'FORM') return;
    var form = element.closest('form[data-confirm]');
    if (form) return; // submit handler owns the confirmation
    var message = confirmationMessage(element);
    if (message && !window.confirm(message)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
}());
