"""Record CSS animations as they start, for tests of the overlay's fades and wipes.

Asking `document.getAnimations()` after "the lights are visible" misses an
animation that already ended in between: an animation without a forwards fill
(the short fades with "reduce motion") is gone from the list the moment it
ends, and a loaded CI runner can easily spend 200 ms between two steps (#246).
`record_animations` notes every animation when it starts, so nothing depends
on how fast the test asks afterwards.
"""

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

RECORD = """(within) => {
    window._animations = [];
    const ms = (t) => parseFloat(t) * (t.endsWith('ms') ? 1 : 1000);
    document.addEventListener('animationstart', (e) => {
        if (!e.target.closest(within)) return;
        // The longhands are comma lists, repeated to the length of animation-name.
        const st = getComputedStyle(e.target);
        const i = st.animationName.split(', ').indexOf(e.animationName);
        const at = (list) => { const v = list.split(', '); return v[i % v.length]; };
        const delay = ms(at(st.animationDelay));
        window._animations.push({
            name: e.animationName,
            cls: e.target.className,
            // Position in the document (tree order), as getAnimations sorts.
            pos: [...document.querySelectorAll('*')].indexOf(e.target),
            delay,
            // As getComputedTiming().endTime: delay + duration x iterations.
            end: delay + ms(at(st.animationDuration)) * parseFloat(at(st.animationIterationCount)),
        });
    });
}"""

DONE = """(within) => window._animations.length > 0 && document.getAnimations()
    .filter((a) => a instanceof CSSAnimation && a.effect && a.effect.target && a.effect.target.closest(within))
    .every((a) => a.playState === 'finished')"""


def record_animations(page, within):
    """From now on, note every CSS animation that starts on or inside the
    elements matching `within` (a selector): name, class and document
    position of its element, delay and end time (ms). Call it before the
    step that starts them."""
    page.evaluate(RECORD, within)


def recorded_animations(page, within, timeout=5000):
    """Wait until an animation has started inside `within` and none of them
    runs or waits for its delay any more, then return what record_animations
    noted. An animation in its delay is still listed by getAnimations, so a
    staggered part that has not started yet is waited for. If none starts
    within `timeout` ms (all animations under test end within 1 s; 5 s
    leaves room for a loaded runner), the list returned is what was noted,
    so the caller's assertion names the failure."""
    try:
        page.wait_for_function(DONE, arg=within, timeout=timeout)
    except PlaywrightTimeoutError:
        pass
    return page.evaluate("() => window._animations")
