import { describe, it, expect } from 'vitest';
import { createSessionStore } from '../../src/iron_verdict/static/js/sessionStore.js';

describe('createSessionStore', () => {
    it('starts with no session, no role, no overlay, disconnected and an empty landing form', () => {
        expect(createSessionStore()).toEqual({
            code: '',
            name: '',
            kind: 'generic',
            role: '',
            isHead: false,
            isDemo: false,
            overlay: false,
            overlayLayoutCode: '',
            overlayNotice: '',
            connectionStatus: 'disconnected',
            serverRestarting: false,
            judgeConnected: { left: false, center: false, right: false },
            roleTakenOver: '',
            newSessionName: '',
            joinCode: '',
            joinError: '',
            joinChecking: false,
        });
    });

    it('gives every store its own judge connectivity object', () => {
        const a = createSessionStore();
        const b = createSessionStore();
        a.judgeConnected.left = true;
        expect(b.judgeConnected.left).toBe(false);
    });
});
