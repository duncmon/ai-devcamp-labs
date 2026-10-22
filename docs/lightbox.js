// Reusable Lightbox for all evidence images across the Walkthrough pages
document.addEventListener('DOMContentLoaded', () => {
  let overlay = document.getElementById('lightboxOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'lightboxOverlay';
    overlay.className = 'lightbox-overlay';
    overlay.innerHTML = `
      <div class="lightbox-content">
        <button class="lightbox-close" id="lightboxClose" aria-label="Close image">&times;</button>
        <img class="lightbox-img" id="lightboxImg" src="" alt="">
        <div class="lightbox-caption" id="lightboxCaption"></div>
      </div>
    `;
    document.body.appendChild(overlay);

    const closeBtn = document.getElementById('lightboxClose');
    const close = () => overlay.classList.remove('active');
    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') close();
    });
  }

  const lightboxImg = document.getElementById('lightboxImg');
  const lightboxCaption = document.getElementById('lightboxCaption');

  document.querySelectorAll('figure.evidence-figure img, .diagram-tile img').forEach(img => {
    img.style.cursor = 'zoom-in';
    img.title = 'Click to expand full size';
    img.addEventListener('click', () => {
      lightboxImg.src = img.src;
      lightboxImg.alt = img.alt;
      const figcap = img.closest('figure')?.querySelector('figcaption');
      lightboxCaption.innerHTML = figcap ? figcap.innerHTML : (img.alt || '');
      overlay.classList.add('active');
    });
  });
});
