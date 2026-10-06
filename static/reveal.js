(() => {
  'use strict';

  function initialize() {
    if (!('IntersectionObserver' in window) || !Element.prototype.animate) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (reducedMotion.matches) return;
    const targets = [...document.querySelectorAll([
      '.hero-main', '.focus-panel', '.section-heading', '.prose > p',
      '.section-title-row', '.job', '.skills-band .eyebrow',
      '#habilidades-title', '.skill-group', '.education-list > article',
      '.courses-title', '.contact > div', '.scheduling-heading'
    ].join(','))];
    const animations = new Map();
    const duration = 760;
    // Prepare offscreen blocks first: never flash visible content and then dim it.
    for (const element of targets) {
      const bounds = element.getBoundingClientRect();
      const visible = bounds.bottom > 0 && bounds.top < window.innerHeight;
      const animation = element.animate([
        {opacity: 0, transform: 'translateY(24px)'},
        {opacity: 1, transform: 'translateY(0)'}
      ], {duration, easing: 'cubic-bezier(0.16, 1, 0.3, 1)', fill: 'both'});
      animation.pause();
      animation.currentTime = visible ? duration : 0;
      animations.set(element, animation);
    }

    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        const element = entry.target;
        const animation = animations.get(element);
        if (!animation) continue;
        if (entry.isIntersecting) {
          if (element.contains(document.activeElement)) animation.finish();
          else animation.play();
        } else {
          // Reset only outside the buffered viewport, never during reading.
          animation.pause();
          animation.currentTime = 0;
        }
      }
    }, {threshold: 0, rootMargin: `${Math.round(window.innerHeight * 0.12)}px 0px`});
    targets.forEach(element => observer.observe(element));

    document.addEventListener('focusin', event => {
      targets.filter(element => element.contains(event.target))
        .forEach(element => animations.get(element)?.finish());
    });
    function disable() {
      observer.disconnect();
      animations.forEach(animation => animation.cancel());
      animations.clear();
    }
    reducedMotion.addEventListener('change', event => {
      if (event.matches) disable();
    });
    window.addEventListener('beforeprint', disable);
    document.querySelectorAll('a[href^="#"]')
      .forEach(link => link.addEventListener('click', () => {
        const destination = document.getElementById(link.hash.slice(1));
        targets.filter(element => destination?.contains(element))
          .forEach(element => animations.get(element)?.finish());
      }));
    // Language restoration runs at load; show the restored reading position.
    window.addEventListener('load', () => requestAnimationFrame(() => {
      targets.filter(element => {
        const bounds = element.getBoundingClientRect();
        return bounds.bottom > 0 && bounds.top < window.innerHeight;
      }).forEach(element => animations.get(element)?.finish());
    }), {once: true});
  }

  // No dependency on Calendly or other external resources finishing their load.
  if (document.readyState !== 'loading') requestAnimationFrame(initialize);
  else document.addEventListener('DOMContentLoaded', () => requestAnimationFrame(initialize), {once: true});
})();
