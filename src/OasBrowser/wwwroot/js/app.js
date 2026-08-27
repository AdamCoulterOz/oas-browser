// The whole JS surface of this app: a hash listener and two accessors.
// Everything else is C#. The clipboard used to be here too; it moved into
// keel, which is the only place in the stack that needs interop.
window.oasBrowser = (() => {
  let handler = null;

  return {
    startHashRouter(dotnet) {
      handler = () => dotnet.invokeMethodAsync('OnHashChanged', location.hash);
      window.addEventListener('hashchange', handler);
      return location.hash;
    },
    stopHashRouter() {
      if (handler) window.removeEventListener('hashchange', handler);
      handler = null;
    },
    setHash(hash) {
      if (location.hash !== hash) location.hash = hash;
    },
    scrollTop() {
      const main = document.querySelector('.shell__main');
      if (main) main.scrollTo({ top: 0 });
      window.scrollTo({ top: 0 });
    }
  };
})();
