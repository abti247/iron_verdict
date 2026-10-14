// How a vote is shown as a light: the light itself is only white (valid) or
// red (invalid); the card colour of an invalid vote (red, blue, yellow) is shown
// as a rectangle under the light (#115). Used by the display and judge stores.

export function lightColor(vote) {
    if (!vote) return null;
    return vote === 'white' ? 'white' : 'red';
}

export function cardColor(vote) {
    return vote && vote !== 'white' ? vote : null;
}
