// VPortal client SDK. Owns the JWT in localStorage and talks to /api/vportal/* on the IV server.
// See docs/superpowers/specs/2026-05-13-vportal-integration-design.md

import {
    QUERY_COMPETITION_ID,
    queryStages,
    queryActiveGroup,
    queryAthletes,
} from './vportalQueries.js';

const FEDERATIONS = {
    BVDK: 'bvdk.vportal-online.de',
    OEVK: 'oevk.vportal-online.de',
};

function storageKey(sessionCode) {
    return `vportal:${sessionCode}`;
}

function readStorage(sessionCode) {
    try {
        const raw = localStorage.getItem(storageKey(sessionCode));
        if (!raw) return null;
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

function writeStorage(sessionCode, value) {
    localStorage.setItem(storageKey(sessionCode), JSON.stringify(value));
}

function clearStorage(sessionCode) {
    localStorage.removeItem(storageKey(sessionCode));
}

async function callProxy(path, payload) {
    const response = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const text = await response.text();
        const error = new Error(`vportal-proxy-error:${response.status}`);
        error.status = response.status;
        error.body = text;
        throw error;
    }
    return response.json();
}

export const vportalClient = {
    FEDERATIONS,

    async login(sessionCode, host, identity, credential) {
        const result = await callProxy('/api/vportal/login', { host, identity, credential });
        writeStorage(sessionCode, {
            host,
            token: result.access_token,
            exp: result.exp,
            fetch_interval_ms: result.fetch_interval_ms,
            competition_id: null,
            stage_id: null,
        });
        return result;
    },

    isConnected(sessionCode) {
        const stored = readStorage(sessionCode);
        if (!stored || !stored.token) return false;
        if (stored.exp && Date.now() / 1000 >= stored.exp) return false;
        return true;
    },

    getStored(sessionCode) {
        return readStorage(sessionCode);
    },

    setStage(sessionCode, stageId, stageName) {
        const stored = readStorage(sessionCode);
        if (!stored) return;
        stored.stage_id = stageId;
        stored.stage_name = stageName;
        writeStorage(sessionCode, stored);
    },

    setCompetitionId(sessionCode, competitionId) {
        const stored = readStorage(sessionCode);
        if (!stored) return;
        stored.competition_id = competitionId;
        writeStorage(sessionCode, stored);
    },

    logout(sessionCode) {
        clearStorage(sessionCode);
    },
};
