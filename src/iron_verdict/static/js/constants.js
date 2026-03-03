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
            "Spotter contact",
            "Technical Non-compliance"
        ]
    },
    bench: {
        red: [
            "Elbow depth",
            "No chest contact"
        ],
        blue: [
            "Downward movement",
            "Arms not locked at completion",
            "Arms not locked before start"
        ],
        yellow: [
            "Incomplete lift",
            "Skipped signal",
            "Buttocks up",
            "Head up",
            "Feet up",
            "Sinking after motionless",
            "Spotter contact",
            "Shoulder / Hand movement",
            "Upper Body thrust",
            "Feet touched bench or supports",
            "Deliberate bar contact with rack supports",
            "Technical Non-compliance"
        ]
    },
    deadlift: {
        red: [
            "Soft knees",
            "Shoulders not back",
            "Failure to stand erect"
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
            "Technical Non-compliance"
        ]
    }
};

export const ROLE_DISPLAY_NAMES = {
    'left_judge': 'Left Judge',
    'center_judge': 'Center Judge (Head)',
    'right_judge': 'Right Judge'
};
