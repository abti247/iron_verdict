// GraphQL queries used by the VPortal integration.
// Copied from github.com/franknitschke/referee server/vportal/queries.js
// (the BVDK referee software) to match the queries that VPortal is known to handle.

export const QUERY_COMPETITION_ID = `{
  profile {
    competition { id }
  }
}`;

export function queryStages(competitionId) {
    return {
        query: `
            query ($competitionId: ID!, $params: CompetitionStageListParams) {
                competitionStageList(competitionId: $competitionId, params: $params) {
                    total
                    competitionStages {
                        id
                        name
                        __typename
                    }
                    __typename
                }
            }
        `,
        variables: { competitionId, params: { limit: 30, start: 0 } },
    };
}

export function queryActiveGroup(competitionId, competitionStageId) {
    return {
        query: `
            query competitionGroupList($competitionId: ID!, $competitionGroupListParams: CompetitionGroupListParams) {
                competitionGroupList(competitionId: $competitionId, params: $competitionGroupListParams) {
                    total
                    competitionGroups {
                        id
                        name
                        active
                        __typename
                    }
                    __typename
                }
            }
        `,
        variables: {
            competitionId,
            competitionGroupListParams: {
                filter: { competitionStageId, active: true },
            },
        },
    };
}

export function queryAthletes(competitionId, competitionStageId, competitionGroupId) {
    return {
        query: `
            query competitionAthleteAttemptList($competitionId: ID!, $competitionAthleteAttemptListParams: CompetitionAthleteAttemptListParams) {
                competitionAthleteAttemptList(competitionId: $competitionId, params: $competitionAthleteAttemptListParams) {
                    total
                    competitionAthleteAttempts {
                        id
                        attempt
                        discipline
                        weight
                        status
                        competitionAthlete {
                            id
                            firstName
                            lastName
                            club { id name __typename }
                            bodyWeightCategory { id name __typename }
                            ageCategory { id name __typename }
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
            }
        `,
        variables: {
            competitionId,
            competitionAthleteAttemptListParams: {
                filter: { competitionGroupId, competitionStageId },
                limit: 3,
            },
        },
    };
}
