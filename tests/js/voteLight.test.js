import { describe, it, expect } from 'vitest';
import { lightColor, cardColor } from '../../src/iron_verdict/static/js/voteLight.js';

describe('lightColor', () => {
    it('shows a white light for a white vote', () => {
        expect(lightColor('white')).toBe('white');
    });

    it.each(['red', 'blue', 'yellow'])('shows a red light for a %s vote', (vote) => {
        expect(lightColor(vote)).toBe('red');
    });

    it('shows no light before the vote', () => {
        expect(lightColor(null)).toBe(null);
    });
});

describe('cardColor', () => {
    it.each(['red', 'blue', 'yellow'])('shows a %s card for a %s vote', (vote) => {
        expect(cardColor(vote)).toBe(vote);
    });

    it('shows no card for a white vote', () => {
        expect(cardColor('white')).toBe(null);
    });

    it('shows no card before the vote', () => {
        expect(cardColor(null)).toBe(null);
    });
});
