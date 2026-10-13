// Maps a failed VPortal login (as thrown by vportalClient) to the message shown
// in the connect dialog. The proxy reports upstream failures as 424 with a fixed
// `reason` code (issue #100); anything else gets a generic message with the
// HTTP status so the operator can still report what happened.

const LOGIN_REASON_KEYS = {
    no_session_cookie: 'vportal.errorNoSession',
    token_exchange_failed: 'vportal.errorTokenExchange',
    missing_access_token: 'vportal.errorMissingToken',
    unreachable: 'vportal.errorUnreachable',
};

function parseDetail(body) {
    try {
        return JSON.parse(body).detail;
    } catch {
        return null;
    }
}

/**
 * @param {Error & {status?: number, body?: string}} err
 * @param {(key: string) => string} t  translation lookup
 * @returns {string}
 */
export function vportalLoginErrorMessage(err, t) {
    // No status: the request never got an HTTP answer from the Iron Verdict server.
    if (err?.status === undefined) return t('vportal.errorServerConnection');
    if (err.status === 401) return t('vportal.loginFailed');
    const detail = err.status === 424 ? parseDetail(err.body) : null;
    const key = detail && LOGIN_REASON_KEYS[detail.reason];
    if (key) return t(key).replace('{status}', String(detail.upstream_status ?? '?'));
    return t('vportal.errorUnexpected').replace('{status}', String(err.status));
}
