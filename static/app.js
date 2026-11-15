document.addEventListener('DOMContentLoaded', () => {
  const menu = document.querySelector('#menu-toggle');
  menu?.addEventListener('click', () => {
    const expanded = document.body.classList.toggle('menu-open');
    menu.setAttribute('aria-expanded', String(expanded));
  });
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  const addButton = document.querySelector('#add-card');
  const total = document.querySelector('#id_cards-TOTAL_FORMS');
  const cards = document.querySelector('#action-cards');
  addButton?.addEventListener('click', () => {
    const index = Number(total.value);
    if (index >= 20) return;
    const template = document.querySelector('#card-template').innerHTML.replaceAll('__prefix__', String(index));
    cards.insertAdjacentHTML('beforeend', template);
    total.value = index + 1;
    addButton.disabled = index + 1 >= 20;
    cards.lastElementChild.querySelector('input:not([type=hidden])')?.focus();
  });
  cards?.addEventListener('click', event => {
    if (!event.target.classList.contains('remove-card')) return;
    const card = event.target.closest('.action-form');
    if (card !== cards.lastElementChild) {
      window.alert('Hapus kartu tambahan dari urutan terakhir terlebih dahulu.');
      return;
    }
    if (!window.confirm('Hapus kartu tambahan ini sebelum dikirim?')) return;
    card.remove();
    total.value = Number(total.value) - 1;
    addButton.disabled = false;
  });
});
