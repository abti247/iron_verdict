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

    async fetchStages(sessionCode) {
        const stored = readStorage(sessionCode);
        if (!stored) throw new Error('vportal-not-connected');

        // Ensure we have the competition ID; fetch once and cache.
        if (!stored.competition_id) {
            const compResp = await callProxy('/api/vportal/graphql', {
                host: stored.host,
                token: stored.token,
                query: QUERY_COMPETITION_ID,
                variables: {},
            });
            stored.competition_id = compResp.data?.profile?.competition?.id;
            writeStorage(sessionCode, stored);
        }

        const { query, variables } = queryStages(stored.competition_id);
        const stagesResp = await callProxy('/api/vportal/graphql', {
            host: stored.host,
            token: stored.token,
            query,
            variables,
        });
        return stagesResp.data?.competitionStageList?.competitionStages ?? [];
    },

    async fetchActiveAttempt(sessionCode) {
        const stored = readStorage(sessionCode);
        if (!stored || !stored.stage_id) throw new Error('vportal-not-configured');

        if (!stored.competition_id) {
            const compResp = await callProxy('/api/vportal/graphql', {
                host: stored.host,
                token: stored.token,
                query: QUERY_COMPETITION_ID,
                variables: {},
            });
            stored.competition_id = compResp.data?.profile?.competition?.id;
            writeStorage(sessionCode, stored);
        }

        const groupReq = queryActiveGroup(stored.competition_id, stored.stage_id);
        const groupResp = await callProxy('/api/vportal/graphql', {
            host: stored.host,
            token: stored.token,
            query: groupReq.query,
            variables: groupReq.variables,
        });
        const groups = groupResp.data?.competitionGroupList?.competitionGroups ?? [];
        if (groups.length === 0) return null;
        const groupId = groups[0].id;

        const athReq = queryAthletes(stored.competition_id, stored.stage_id, [groupId]);
        const athResp = await callProxy('/api/vportal/graphql', {
            host: stored.host,
            token: stored.token,
            query: athReq.query,
            variables: athReq.variables,
        });
        const attempts = athResp.data?.competitionAthleteAttemptList?.competitionAthleteAttempts ?? [];
        if (attempts.length === 0) return null;
        const a = attempts[0];
        return {
            firstName: a.competitionAthlete?.firstName ?? '',
            lastName: a.competitionAthlete?.lastName ?? '',
            club: a.competitionAthlete?.club?.name ?? '',
            bodyWeightCategory: a.competitionAthlete?.bodyWeightCategory?.name ?? '',
            ageCategory: a.competitionAthlete?.ageCategory?.name ?? '',
            discipline: a.discipline ?? '',
            attempt: a.attempt ?? null,
            weight: a.weight ?? null,
        };
    },
};
