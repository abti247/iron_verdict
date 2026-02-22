export const CARD_REASONS = {
    squat: {
        red: [
            "Depth"
        ],
        blue: [
            "Soft knees",
            "Downward movement"
        ],
        yellow: [
            "Incomplete lift",
            "Skipped signal",
            "Foot movement",
            "Dropped bar",
            "Supporting contact on legs",
            "Spotter contact"
        ]
    },
    bench: {
        red: [
            "Elbow depth",
            "No chest contact"
        ],
        blue: [
            "Downward movement",
            "Arms not locked"
        ],
        yellow: [
            "Incomplete lift",
            "Skipped signal",
            "Buttocks up",
            "Head up",
            "Feet up",
            "Spotter contact",
            "Shoulder / Hand movement",
            "Heaving / Body thrust",
            "Feet touched bench or supports",
            "Deliberate bar contact with rack supports"
        ]
    },
    deadlift: {
        red: [
            "Soft knees",
            "Shoulders not back"
        ],
        blue: [
            "Hitching",
            "Downward movement"
        ],
        yellow: [
            "Incomplete lift",
            "Dropped bar",
            "Skipped signal",
            "Foot movement",
            "Spotter contact"
        ]
    }
};

export const ROLE_DISPLAY_NAMES = {
    'left_judge': 'Left Judge',
    'center_judge': 'Center Judge (Head)',
    'right_judge': 'Right Judge'
};
