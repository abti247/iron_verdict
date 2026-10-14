import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { CARD_REASONS } from '../../src/iron_verdict/static/js/constants.js';

// Reason keys are sent over the wire and translated on the display. A key
// missing from a locale would be shown raw, so every offered reason must
// resolve in every language.
const LOCALES = ['en', 'de'];

function lookup(obj, key) {
    return key.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

const allKeys = Object.values(CARD_REASONS)
    .flatMap(byColor => Object.values(byColor))
    .flat();

describe('reason catalog', () => {
    for (const lang of LOCALES) {
        const file = resolve(__dirname, `../../src/iron_verdict/static/locales/${lang}.json`);
        const messages = JSON.parse(readFileSync(file, 'utf-8'));

        it(`every offered reason has a ${lang} text`, () => {
            const missing = allKeys.filter(key => typeof lookup(messages, key) !== 'string');
            expect(missing).toEqual([]);
        });
    }

    it('bench yellow lists head/shoulders and hand movement as separate reasons, in rulebook order', () => {
        const yellow = CARD_REASONS.bench.yellow;
        expect(yellow).not.toContain('reasons.bench.yellow.headUp');
        expect(yellow).not.toContain('reasons.bench.yellow.shoulderHandMovement');
        const buttocks = yellow.indexOf('reasons.bench.yellow.buttocksUp');
        expect(yellow.slice(buttocks, buttocks + 3)).toEqual([
            'reasons.bench.yellow.buttocksUp',
            'reasons.bench.yellow.headShouldersUp',
            'reasons.bench.yellow.handMovement',
        ]);
    });
});
