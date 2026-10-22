/**
 * Social Spark — Dynamic Right-Hand TOC Sidebar & Floating Back-to-Top
 * Pure Vanilla ES6 — Cross-browser compatible (Chrome, Safari, Firefox, Edge, iOS, Android)
 */
(function() {
  'use strict';

  function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
      tag => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
      }[tag] || tag)
    );
  }

  function initBackToTop() {
    if (document.getElementById('backToTopBtn')) return;
    const btn = document.createElement('button');
    btn.id = 'backToTopBtn';
    btn.className = 'back-to-top';
    btn.setAttribute('aria-label', 'Return to top of page');
    btn.setAttribute('title', 'Return to top');
    btn.innerHTML = '↑';
    document.body.appendChild(btn);

    let ticking = false;
    window.addEventListener('scroll', function() {
      if (!ticking) {
        window.requestAnimationFrame(function() {
          if (window.scrollY > 300) {
            btn.classList.add('visible');
          } else {
            btn.classList.remove('visible');
          }
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });

    btn.addEventListener('click', function() {
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    });
  }

  function initTOC() {
    const main = document.querySelector('main');
    if (!main) {
      initBackToTop();
      return;
    }

    // Identify all step cards or major sections
    const sections = Array.from(main.querySelectorAll('article.step-card, section.step-card'));
    if (sections.length < 2) {
      initBackToTop();
      return;
    }

    // Check if layout wrapper already exists, or wrap dynamically
    let pageLayout = main.querySelector('.page-layout');
    let pageMain = main.querySelector('.page-main');
    let tocSidebar = main.querySelector('.toc-sidebar');

    if (!pageLayout) {
      pageLayout = document.createElement('div');
      pageLayout.className = 'page-layout';
      pageMain = document.createElement('div');
      pageMain.className = 'page-main';

      // Move children into pageMain
      while (main.firstChild) {
        pageMain.appendChild(main.firstChild);
      }

      pageLayout.appendChild(pageMain);
      main.appendChild(pageLayout);
    }

    if (!tocSidebar) {
      tocSidebar = document.createElement('aside');
      tocSidebar.className = 'toc-sidebar';
      pageLayout.appendChild(tocSidebar);
    }

    // Build TOC content
    tocSidebar.innerHTML = '';
    const tocHeader = document.createElement('div');
    tocHeader.className = 'toc-header';
    tocHeader.innerHTML = '<span>📑</span> <span>On this page</span>';
    tocSidebar.appendChild(tocHeader);

    const tocList = document.createElement('ul');
    tocList.className = 'toc-list';

    const items = [];

    sections.forEach(function(sec, idx) {
      // Ensure section has an anchor id
      if (!sec.id) {
        const stepNumEl = sec.querySelector('.step-num');
        if (stepNumEl && stepNumEl.textContent.trim()) {
          const numText = stepNumEl.textContent.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-');
          sec.id = numText.startsWith('step') ? numText : ('step-' + numText);
        } else {
          sec.id = 'section-' + (idx + 1);
        }
      }

      const titleEl = sec.querySelector('.step-title') || sec.querySelector('h2') || sec.querySelector('h3');
      if (!titleEl) return;

      const stepNumEl = sec.querySelector('.step-num');
      const stepNumText = stepNumEl ? stepNumEl.textContent.trim() : '';
      const titleText = titleEl.textContent.trim();

      const li = document.createElement('li');
      li.className = 'toc-item';

      const a = document.createElement('a');
      a.href = '#' + sec.id;
      a.className = 'toc-link';
      if (stepNumText) {
        a.innerHTML = '<span class="toc-badge">' + escapeHTML(stepNumText) + '</span> ' + escapeHTML(titleText);
      } else {
        a.textContent = titleText;
      }

      li.appendChild(a);
      tocList.appendChild(li);

      items.push({ id: sec.id, element: sec, link: a });
    });

    tocSidebar.appendChild(tocList);

    // Scroll Spy using IntersectionObserver with fallback
    if ('IntersectionObserver' in window && items.length > 0) {
      let currentActiveId = null;

      const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          if (entry.isIntersecting) {
            currentActiveId = entry.target.id;
          }
        });

        if (currentActiveId) {
          items.forEach(function(item) {
            if (item.id === currentActiveId) {
              item.link.classList.add('active');
            } else {
              item.link.classList.remove('active');
            }
          });
        }
      }, {
        rootMargin: '-70px 0px -65% 0px',
        threshold: 0
      });

      items.forEach(function(item) {
        observer.observe(item.element);
      });
    }

    initBackToTop();
  }

  // Auto-initialize when ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTOC);
  } else {
    initTOC();
  }
})();
