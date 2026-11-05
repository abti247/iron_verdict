import { describe, it, expect, vi } from 'vitest';
import { roleSelectScreen } from '../../src/iron_verdict/static/js/screens/roleSelectScreen.js';

// The session-code link on role select (#212): only Ctrl/Cmd+click lets the browser
// open it; every other click is swallowed (middle click is auxclick, the context
// menu no click at all).
function click(mods = {}) {
    return { ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...mods, preventDefault: vi.fn() };
}

describe('session-code link click', () => {
    const screen = roleSelectScreen({});

    it.each([
        ['plain click', {}],
        ['Shift+click (new window)', { shiftKey: true }],
        ['Alt+click (download)', { altKey: true }],
    ])('swallows a %s', (_name, mods) => {
        const event = click(mods);
        screen.onCodeClick(event);
        expect(event.preventDefault).toHaveBeenCalled();
    });

    it.each([
        ['Ctrl+click', { ctrlKey: true }],
        ['Cmd+click', { metaKey: true }],
    ])('lets a %s open the link', (_name, mods) => {
        const event = click(mods);
        screen.onCodeClick(event);
        expect(event.preventDefault).not.toHaveBeenCalled();
    });
});
