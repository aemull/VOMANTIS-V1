document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('img[data-fallback-src]').forEach(img => {
    const fallback = () => {
      if (!img.dataset.fallbackSrc) return;
      img.src = img.dataset.fallbackSrc;
      img.alt = `Foto belum tersedia: ${img.alt}`;
      delete img.dataset.fallbackSrc;
    };
    img.addEventListener('error', fallback, { once: true });
    if (img.complete && img.naturalWidth === 0) fallback();
  });
  const menu = document.querySelector('#menu-toggle');
  const sidebar = document.querySelector('#app-sidebar');
  const mobileLayout = window.matchMedia('(max-width: 960px)');
  const setMenu = expanded => {
    document.body.classList.toggle('menu-open', expanded);
    menu?.setAttribute('aria-expanded', String(expanded));
    menu?.setAttribute('aria-label', expanded ? 'Tutup menu' : 'Buka menu');
    if (sidebar) sidebar.inert = mobileLayout.matches && !expanded;
  };
  menu?.addEventListener('click', () => setMenu(!document.body.classList.contains('menu-open')));
  document.querySelector('.menu-backdrop')?.addEventListener('click', () => {
    setMenu(false);
    menu?.focus();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('menu-open')) {
      setMenu(false);
      menu?.focus();
    }
  });
  mobileLayout.addEventListener('change', () => setMenu(false));
  setMenu(false);
  const gallery = document.querySelector('.gallery-dialog');
  const photos = [...document.querySelectorAll('[data-gallery-photo]')];
  if (gallery && typeof gallery.showModal === 'function' && photos.length) {
    let current = 0;
    const showPhoto = index => {
      current = (index + photos.length) % photos.length;
      const photo = photos[current];
      const preview = gallery.querySelector('[data-gallery-image]');
      preview.src = photo.href;
      preview.alt = photo.querySelector('img').alt;
      gallery.querySelector('[data-gallery-caption]').textContent = preview.alt;
      gallery.querySelector('[data-gallery-counter]').textContent = `${current + 1} / ${photos.length}`;
    };
    photos.forEach((photo, index) => photo.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      showPhoto(index);
      gallery.showModal();
    }));
    gallery.querySelector('[data-gallery-close]').addEventListener('click', () => gallery.close());
    const previous = gallery.querySelector('[data-gallery-prev]');
    const next = gallery.querySelector('[data-gallery-next]');
    previous.disabled = next.disabled = photos.length < 2;
    previous.addEventListener('click', () => showPhoto(current - 1));
    next.addEventListener('click', () => showPhoto(current + 1));
    gallery.addEventListener('keydown', event => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        showPhoto(current + (event.key === 'ArrowLeft' ? -1 : 1));
      }
    });
  }
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
