import { describe, it, expect } from 'vitest';
import { vportalLoginErrorMessage } from '../../src/iron_verdict/static/js/vportalErrors.js';

// Identity-ish translator: returns the key, keeping {status} placeholders visible.
const KEYS = {
    'vportal.loginFailed': 'bad-credentials',
    'vportal.errorNoSession': 'no-session',
    'vportal.errorTokenExchange': 'token-exchange {status}',
    'vportal.errorMissingToken': 'missing-token',
    'vportal.errorUnreachable': 'unreachable',
    'vportal.errorServerConnection': 'server-connection',
    'vportal.errorUnexpected': 'unexpected {status}',
};
const t = (key) => KEYS[key] ?? key;

function proxyError(status, body) {
    const err = new Error(`vportal-proxy-error:${status}`);
    err.status = status;
    err.body = typeof body === 'string' ? body : JSON.stringify(body);
    return err;
}

describe('vportalLoginErrorMessage', () => {
    it('maps 401 to the wrong-credentials message', () => {
        expect(vportalLoginErrorMessage(proxyError(401, { detail: 'Invalid VPortal credentials' }), t))
            .toBe('bad-credentials');
    });

    it.each([
        ['no_session_cookie', 'no-session'],
        ['missing_access_token', 'missing-token'],
        ['unreachable', 'unreachable'],
    ])('maps 424 reason %s to its message', (reason, expected) => {
        expect(vportalLoginErrorMessage(proxyError(424, { detail: { reason } }), t)).toBe(expected);
    });

    it('includes the upstream status for a failed token exchange', () => {
        const err = proxyError(424, { detail: { reason: 'token_exchange_failed', upstream_status: 500 } });
        expect(vportalLoginErrorMessage(err, t)).toBe('token-exchange 500');
    });

    it('falls back to the generic message for an unknown reason', () => {
        expect(vportalLoginErrorMessage(proxyError(424, { detail: { reason: 'new_thing' } }), t))
            .toBe('unexpected 424');
    });

    it('falls back to the generic message with status for a non-JSON body', () => {
        expect(vportalLoginErrorMessage(proxyError(502, '<html>Bad gateway</html>'), t))
            .toBe('unexpected 502');
    });

    it('reports a lost connection to the server when fetch itself failed', () => {
        expect(vportalLoginErrorMessage(new TypeError('Failed to fetch'), t)).toBe('server-connection');
    });
});
