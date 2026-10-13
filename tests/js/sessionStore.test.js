import { describe, it, expect } from 'vitest';
import { createSessionStore } from '../../src/iron_verdict/static/js/sessionStore.js';

describe('createSessionStore', () => {
    it('starts with no session, no role and disconnected', () => {
        expect(createSessionStore()).toEqual({
            code: '',
            name: '',
            kind: 'generic',
            role: '',
            isHead: false,
            connectionStatus: 'disconnected',
            serverRestarting: false,
            judgeConnected: { left: false, center: false, right: false },
        });
    });

    it('gives every store its own judge connectivity object', () => {
        const a = createSessionStore();
        const b = createSessionStore();
        a.judgeConnected.left = true;
        expect(b.judgeConnected.left).toBe(false);
    });
});
