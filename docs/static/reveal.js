(() => {
  'use strict';

  function initialize() {
    if (!('IntersectionObserver' in window) || !Element.prototype.animate) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const targets = [...document.querySelectorAll([
      '.hero-main', '.focus-panel', '.section-heading', '.prose > p',
      '.section-title-row', '.job', '.skills-band .eyebrow',
      '#habilidades-title', '.skill-group', '.education-list > article',
      '.courses-title', '.contact > div', '.scheduling-heading'
    ].join(','))];
    const initialViewport = new Set(targets.filter(element => {
      const bounds = element.getBoundingClientRect();
      return bounds.bottom > 0 && bounds.top < window.innerHeight;
    }));
    const animations = new Map();

    function cancel(element) {
      animations.get(element)?.cancel();
      animations.delete(element);
    }

    // Content stays visible by default, including when JavaScript is unavailable.
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        const element = entry.target;
        if (!entry.isIntersecting) {
          cancel(element);
          initialViewport.delete(element);
          continue;
        }
        if (initialViewport.delete(element) || reducedMotion.matches ||
            element.contains(document.activeElement)) continue;
        cancel(element);
        const distance = entry.boundingClientRect.top < 0 ? -18 : 18;
        const animation = element.animate([
          {opacity: 0.25, transform: `translateY(${distance}px)`},
          {opacity: 1, transform: 'translateY(0)'}
        ], {duration: 620, easing: 'cubic-bezier(0.22, 1, 0.36, 1)'});
        animations.set(element, animation);
        animation.onfinish = () => {
          if (animations.get(element) === animation) animations.delete(element);
        };
      }
    }, {threshold: 0, rootMargin: '0px 0px -6% 0px'});
    targets.forEach(element => observer.observe(element));

    document.addEventListener('focusin', event => {
      targets.filter(element => element.contains(event.target)).forEach(cancel);
    });
    const cancelAll = () => [...animations.keys()].forEach(cancel);
    reducedMotion.addEventListener('change', cancelAll);
    window.addEventListener('beforeprint', cancelAll);
    window.addEventListener('pagehide', cancelAll);
  }

  // Wait for anchor and language-position restoration before observing sections.
  if (document.readyState === 'complete') requestAnimationFrame(initialize);
  else window.addEventListener('load', () => requestAnimationFrame(initialize), {once: true});
})();
