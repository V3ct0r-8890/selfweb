/*
 * Shared colour theme for the launcher and every tool: Device default / Light / Dark.
 *
 * The choice is stored once, in localStorage 'selfweb-theme' ('auto' | 'light' | 'dark'),
 * and every page on this site reads it. The resolved theme is written to
 * <html data-app-theme="light|dark"> (a name no tool used before, so it cannot clash
 * with a tool's own theme code) and to color-scheme, which darkens native controls.
 *
 * A change made in one page reaches the others already open (the tool inside the
 * launcher's frame) through the storage event. Tools with their own theme switch
 * listen for the 'selfweb-theme' window event and call selfwebTheme.set().
 *
 * Load it with a plain <script> in <head>, before any styles render, so a dark page
 * never flashes white first.
 */
(function () {
    const KEY = 'selfweb-theme';
    const CHOICES = ['auto', 'light', 'dark'];
    const deviceDark = window.matchMedia('(prefers-color-scheme: dark)');
    let applied = null;

    function choice() {
        try {
            const saved = localStorage.getItem(KEY);
            return CHOICES.includes(saved) ? saved : 'auto';
        } catch (e) {
            return 'auto'; // storage blocked (private mode): follow the device
        }
    }

    function resolved() {
        const c = choice();
        return c === 'auto' ? (deviceDark.matches ? 'dark' : 'light') : c;
    }

    function apply() {
        const theme = resolved();
        const root = document.documentElement;
        root.setAttribute('data-app-theme', theme);
        root.style.colorScheme = theme;
        if (theme === applied) return;
        applied = theme;
        window.dispatchEvent(new CustomEvent('selfweb-theme', { detail: { theme } }));
    }

    window.selfwebTheme = {
        choice,
        resolved,
        isDark: () => resolved() === 'dark',
        set(value) {
            if (!CHOICES.includes(value)) return;
            try { localStorage.setItem(KEY, value); }
            catch (e) { console.warn('[theme] choice not saved:', e); }
            apply();
        },
    };

    apply();
    deviceDark.addEventListener('change', apply);
    window.addEventListener('storage', (e) => { if (e.key === KEY || e.key === null) apply(); });
})();
